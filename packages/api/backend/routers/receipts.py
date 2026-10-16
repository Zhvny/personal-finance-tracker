"""
backend/routers/receipts.py — Receipt Reader routes (CLI OCR ensemble)
=======================================================================
Extracted from api_server.py as part of Step 5 router split.
Architecture: High Cohesion — this file owns only /api/receipt routes.
Low Coupling : depends only on backend/routers/deps.py and FastAPI. Never imports other routers.
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from packages.api.backend.routers.deps import (
    _check_and_apply_reward_unlocks,
    _db,
    _execute,
)
from packages.api.backend.security.core import require_scope
from packages.core.application.receipt_reader.categorizer import UniversalCategorizer
from packages.core.application.receipt_reader.ocr_ensemble import OCREnsemble
from packages.core.application.receipt_reader.parser import ReceiptParser

router = APIRouter(dependencies=[Depends(require_scope("write"))])
logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════
# RECEIPT READER
# ═════════════════════════════════════════════════════════════════════

@router.post("/api/receipt/scan")
async def scan_receipt(file: UploadFile = File(...), ocr_engine: Optional[str] = Form(None)):
    """
    Accept an image upload, run OCR + parse via the CLI's OCR ensemble,
    and return structured ReceiptData as JSON.
    """
    # ── Security: validate MIME type and extension ──────────────────────────
    _ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp", "application/pdf"}
    _ALLOWED_EXT  = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".pdf"}
    _MAX_BYTES    = 10 * 1024 * 1024  # 10 MB

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in _ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Invalid file type. Only images are accepted.")

    raw_suffix = Path(file.filename or "").suffix.lower()
    if raw_suffix not in _ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Invalid file extension.")
    suffix = raw_suffix or ".jpg"

    import tempfile
    tmp_path = None
    try:
        raw_bytes = await file.read(_MAX_BYTES + 1)
        if len(raw_bytes) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if len(raw_bytes) > _MAX_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Maximum 10 MB.")
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw_bytes)
            tmp_path = tmp.name

        ensemble    = OCREnsemble(language="id", use_gpu=False)
        parser      = ReceiptParser()
        categorizer = UniversalCategorizer()

        result = await asyncio.to_thread(ensemble.run, tmp_path, verbose=False, engine_name=ocr_engine)

        if not result.best_text.strip():
            raise HTTPException(status_code=400, detail="No text detected in receipt image.")

        receipts = parser.parse_all(result.best_text)
        for r in receipts:
            r.confidence_score = result.confidence
            r.metadata["engine"] = result.best_engine
            clf = categorizer.classify(r)
            r.category = clf.category

        def _serialize(r):
            return {
                "merchant_name":    r.merchant_name,
                "transaction_date": r.transaction_date.isoformat(),
                "total_amount":     r.total_amount.amount,
                "currency":         r.total_amount.currency,
                "payment_method":   r.payment_method.value if r.payment_method else None,
                "transaction_type": r.transaction_type.value,
                "category":         r.category.value if hasattr(r.category, "value") else str(r.category),
                "confidence":       r.confidence_score,
                "engine":           r.metadata.get("engine", "?"),
                "document_type":    r.metadata.get("document_type", "STRUK"),
                "doc_type_label":   r.metadata.get("doc_type_label", "Struk / Receipt"),
                "items":            [{"name": i.name, "qty": i.quantity, "total": i.total_price.amount}
                                     for i in (r.items or [])],
            }

        return {"ok": True, "receipts": [_serialize(r) for r in receipts],
                "engine_ranking": result.engine_ranking}

    except HTTPException:
        raise
    except Exception:
        logger.exception("Receipt scan error")
        return {"ok": False, "error": "Receipt scan failed. Please try again.", "receipts": []}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/api/receipt/export")
def export_receipt(body: dict):
    """
    Export a parsed receipt dict to expense_tracker or income_tracker DB.
    body: { target: "expense"|"income", receipt: {...} }
    """
    target  = body.get("target")
    receipt = body.get("receipt", {})

    date_raw = receipt.get("transaction_date", datetime.now().isoformat())[:10]
    amount   = receipt.get("total_amount", 0)
    merchant = receipt.get("merchant_name", "Unknown")
    category = receipt.get("category", "other")
    payment  = receipt.get("payment_method") or "cash"

    # Use description from metadata if available (for "Pocket Money" etc)
    description = receipt.get("metadata", {}).get("description_hint") or merchant

    if target == "expense":
        db = _db("expense_tracker", "expense.db")
        new_id = _execute(db,
            "INSERT INTO expenses (amount,description,category,payment_method,date)"
            " VALUES (?,?,?,?,?)",
            (amount, description, category, payment, date_raw))
        auto_unlocked = _check_and_apply_reward_unlocks()
        return {"ok": True, "id": new_id, "target": "expense", "auto_unlocked": auto_unlocked}

    elif target == "income":
        db = _db("income_tracker", "income.db")
        # Ensure income_type is normalized and valid
        income_type = receipt.get("category", "other").lower()
        if income_type == "uncategorized":
            income_type = "other"

        new_id = _execute(db,
            "INSERT INTO incomes (amount,source,income_type,date)"
            " VALUES (?,?,?,?)",
            (amount, description, income_type, date_raw))
        auto_unlocked = _check_and_apply_reward_unlocks()
        return {"ok": True, "id": new_id, "target": "income", "auto_unlocked": auto_unlocked}

    raise HTTPException(400, "target must be 'expense' or 'income'")


