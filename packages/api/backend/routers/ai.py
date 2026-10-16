"""
backend/routers/ai.py â€” AI Engine routes
==========================================
Route handlers only. All provider logic and data aggregation
live in dedicated modules:

  backend/ai/provider_strategy.py      â€” _detect_provider, _ai_chat, _ai_chat_vision,
                                           JSON repair, prompt templates, state globals
  backend/behavioral/data_aggregator.py â€” _gather_financial_data, _build_financial_context

Architecture: High Cohesion â€” this file owns only AI route handlers.
Low Coupling : depends on provider_strategy + data_aggregator, never on other routers.

Routes:
  GET  /api/ai/status           â€” active provider, model, capabilities
  POST /api/ai/provider         â€” force-switch provider at runtime
  POST /api/receipt/scan-ai     â€” Claude Vision / Ollama+OCR receipt scan
  GET  /api/ai/insights         â€” behavioral finance AI analysis
  GET  /api/ai/insights/stream  â€” SSE streaming insights
"""

import asyncio
import json
import logging
import os
import re
import urllib.error as _urlerr
import urllib.request as _urlreq
from datetime import date, datetime
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import packages.api.backend.ai.provider_strategy as _ps
from packages.api.backend.ai.provider_strategy import (
    _INSIGHTS_SYSTEM_SMALL,
    _RECEIPT_SYSTEM,
    _ai_chat,
    _ai_chat_vision,
    _anthropic_key,
    _detect_provider,
    _insights_system_for,
    _insights_tokens_for,
    _load_rule_engine,
    _load_receipt_parser,
    _ollama_available,
    _ollama_base,
    _ollama_token_cap,
    _repair_truncated_json,
    _strip_json_fences,
)
from packages.api.backend.behavioral.data_aggregator import (
    _format_financial_context,
    _gather_financial_data,
)
from packages.api.backend.routers.deps import (
    _get_merchant_memory,
)
from packages.api.backend.security.core import require_scope
from packages.core.application.receipt_reader.parser import detect_document_type

router = APIRouter(dependencies=[Depends(require_scope("read"))])
logger = logging.getLogger(__name__)


@router.get("/api/ai/status")
def ai_status():
    """
    Return the active AI provider, model, capabilities, and availability of all providers.
    Used by the frontend to display the AI status badge.
    Includes ollama_models: list of models actually installed on this machine.
    """
    info = _detect_provider()
    ollama_ok, ollama_model = _ollama_available()

    # Fetch the real installed model list from Ollama â€” used by UI model picker
    ollama_models = []
    if ollama_ok:
        try:
            req = _urlreq.Request(f"{_ollama_base()}/api/tags", method="GET")
            with _urlreq.urlopen(req, timeout=3) as resp:
                tags_data = json.loads(resp.read())
            for m in tags_data.get("models", []):
                name = m.get("name", "")
                size_bytes = m.get("size", 0)
                size_gb = round(size_bytes / 1_073_741_824, 1) if size_bytes else None
                ollama_models.append(
                    {
                        "id": name,
                        "label": name,
                        "size": f"{size_gb} GB" if size_gb else None,
                    }
                )
        except Exception:
            logger.exception("Error while loading cached AI context")
            pass  # Ollama might have gone down between check and fetch

    return {
        "active": info["provider"],
        "status_code": 200,
        "timestamp": datetime.now().isoformat(),
        "model": info["model"],
        "vision": info["vision"],
        "reason": info["reason"],
        "override": _ps._PROVIDER_OVERRIDE,
        "claude_available": bool(_anthropic_key()),
        "gemini_available": bool(_ps._gemini_key()),
        "ollama_available": ollama_ok,
        "ollama_model": ollama_model,
        "ollama_models": ollama_models,  # real installed models â€” used by UI picker
        "rules_available": True,
        "rules_model": "rule-engine-v1",
    }


@router.post("/api/ai/provider", dependencies=[Depends(require_scope("write"))])
def set_ai_provider(body: dict):
    """
    Force-switch AI provider at runtime.
    body: { "provider": "auto" | "claude" | "gemini" | "ollama" | "rules", "model": "llama3.1:8b" (optional) }
    Mutations go to backend/ai/provider_strategy globals via _ps module reference.
    """
    p = body.get("provider", "auto")
    m = body.get("model", None)
    if p not in ("auto", "claude", "gemini", "ollama", "rules"):
        raise HTTPException(400, "provider harus 'auto', 'claude', 'gemini', 'ollama', atau 'rules'")
    _ps._PROVIDER_OVERRIDE = None if p == "auto" else p
    _ps._OLLAMA_MODEL_CACHE = None  # force re-detection
    if m:
        if p == "gemini":
            _ps._GEMINI_MODEL_OVERRIDE = m
        else:
            _ps._OLLAMA_MODEL_OVERRIDE = m
    elif p in ("auto", "claude", "gemini", "rules"):
        _ps._OLLAMA_MODEL_OVERRIDE = None
        _ps._GEMINI_MODEL_OVERRIDE = None
    info = _detect_provider()
    return {
        "ok": True,
        "active": info["provider"],
        "status_code": 200,
        "timestamp": datetime.now().isoformat(),
        "model": info["model"],
        "vision": info["vision"],
    }


def _clean_idr_amount(val) -> float:
    """Robustly parse IDR numbers in various formats: 150.000, 150000, Rp 150.000,00, 150,000.00, etc."""
    if isinstance(val, (int, float)):
        return float(val)
    if not val:
        return 0.0
    s = str(val).strip()
    s = re.sub(r'^(?:rp|idr\.?|usd)\s*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'[^\d.,]', '', s).strip()
    if not s:
        return 0.0

    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        parts = s.split(',')
        if len(parts[-1]) == 2:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    elif '.' in s:
        parts = s.split('.')
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            s = s.replace('.', '')
    try:
        return float(s)
    except ValueError:
        return 0.0


def _preprocess_receipt_image(raw_bytes: bytes) -> tuple[bytes, str]:
    """Auto-rotate EXIF orientation, resize if >2048px, and return cleaned JPEG bytes + b64."""
    import base64 as _b64
    import io as _io
    try:
        from PIL import Image, ImageOps
        img = Image.open(_io.BytesIO(raw_bytes))
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        max_dim = 2048
        w, h = img.size
        if max(w, h) > max_dim:
            ratio = max_dim / float(max(w, h))
            new_size = (int(w * ratio), int(h * ratio))
            resample_mode = getattr(Image, "Resampling", Image).LANCZOS
            img = img.resize(new_size, resample_mode)
        out = _io.BytesIO()
        img.save(out, format="JPEG", quality=92)
        proc_bytes = out.getvalue()
        b64_str = _b64.standard_b64encode(proc_bytes).decode("utf-8")
        return proc_bytes, b64_str
    except Exception as e:
        logger.warning(f"Image preprocessing fallback: {e}")
        b64_str = _b64.standard_b64encode(raw_bytes).decode("utf-8")
        return raw_bytes, b64_str

# â”€â”€ Receipt Scanner (AI-powered) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/api/receipt/scan-ai", dependencies=[Depends(require_scope("write"))])
async def scan_receipt_ai(file: UploadFile = File(...), ocr_engine: Optional[str] = Form(None)):
    """
    AI-powered receipt scanner.
    Claude: direct Vision (multimodal) â€” most accurate.
    Ollama: pytesseract OCR â†’ text sent to LLM for structured extraction.
    Falls back gracefully; returns same schema as /api/receipt/scan.
    """

    # Support manual engine/provider override from frontend selector
    forced_provider = None
    if ocr_engine:
        e_low = ocr_engine.lower()
        if "claude" in e_low:
            forced_provider = "claude"
        elif "gemini" in e_low:
            forced_provider = "gemini"
        elif "ollama" in e_low:
            forced_provider = "ollama"
        elif "rules" in e_low or "offline" in e_low:
            forced_provider = "rules"

    # Temporarily override if requested
    if forced_provider:
        old_override = _ps._PROVIDER_OVERRIDE
        _ps._PROVIDER_OVERRIDE = forced_provider
        try:
            info = _detect_provider()
        finally:
            _ps._PROVIDER_OVERRIDE = old_override
    else:
        info = _detect_provider()

    if info["provider"] == "none":
        logger.error(f"AI Provider not available: {info['reason']}")
        raise HTTPException(503, info["reason"])

    # ── Security: validate MIME type and extension ──────────────────────────
    _ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"}
    _ALLOWED_EXT  = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
    _MAX_BYTES    = 10 * 1024 * 1024  # 10 MB
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in _ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Invalid file type. Only images are accepted.")
    raw_suffix = Path(file.filename or "").suffix.lower()
    if raw_suffix not in _ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Invalid file extension.")
    suffix = raw_suffix or ".jpg"

    tmp_path = None
    try:
        raw_bytes = await file.read(_MAX_BYTES + 1)
        if len(raw_bytes) > _MAX_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Maximum 10 MB.")

        proc_bytes, image_b64 = _preprocess_receipt_image(raw_bytes)

        # ── Rule-based path: OCR → pattern matching ───────────────────────
        if info["provider"] == "rules":
            eng = _load_rule_engine()
            if not eng:
                return {"ok": False, "error": "Rule engine tidak tersedia.", "receipts": []}
            ocr_text = ""
            ocr_err_msg = None
            try:
                import io

                import PIL.Image
                import pytesseract
                img = PIL.Image.open(io.BytesIO(proc_bytes))
                ocr_text = pytesseract.image_to_string(img, lang="ind+eng")
            except Exception as e:
                ocr_err_msg = str(e)
                logger.exception("[scan-ai] Rule-based OCR failed")

            parsed = (_load_receipt_parser() or eng).rule_based_receipt_parse(ocr_text or "")
            mm = _get_merchant_memory()
            if mm and hasattr(mm, "enrich_receipt_category"):
                parsed = mm.enrich_receipt_category(parsed)
            parsed["engine"] = "rule-engine-v1"
            parsed["ai_analysis"] = (
                "Diproses menggunakan rule-based engine (offline mode). "
                + (f"Peringatan: OCR gagal ({ocr_err_msg}). " if ocr_err_msg else "")
                + "Verifikasi dan koreksi data di bawah sebelum menyimpan."
            )
            return {
                "ok": True,
                "receipts": [parsed],
                "engine_ranking": ["rule-engine-v1"],
                "ai_powered": True,
                "provider": "rules",
            }

        # ── LLM path (Claude or Ollama) ───────────────────────────────────
        user_prompt = (
            "Tolong baca struk/receipt ini dan ekstrak semua informasi "
            "transaksi dalam format JSON yang sudah ditentukan."
        )
        try:
            raw = await asyncio.to_thread(_ai_chat_vision, _RECEIPT_SYSTEM, user_prompt, image_b64, "image/jpeg")
        except HTTPException as llm_err:
            logger.warning(f"[scan-ai] LLM failed ({llm_err.detail}), falling back to rule engine")
            eng = _load_rule_engine()
            if not eng:
                raise
            ocr_text = ""
            ocr_err_msg = None
            try:
                import io as _io

                import PIL.Image
                import pytesseract
                img = PIL.Image.open(_io.BytesIO(proc_bytes))
                ocr_text = pytesseract.image_to_string(img, lang="ind+eng")
            except Exception as e:
                ocr_err_msg = str(e)
                logger.exception("[scan-ai] Fallback OCR failed")

            parsed = (_load_receipt_parser() or eng).rule_based_receipt_parse(ocr_text or "")
            mm = _get_merchant_memory()
            if mm and hasattr(mm, "enrich_receipt_category"):
                parsed = mm.enrich_receipt_category(parsed)
            parsed["engine"] = "rule-engine-v1"
            parsed["ai_analysis"] = (
                "Diproses menggunakan rule-based engine (AI tidak tersedia). "
                + (f"Peringatan: OCR gagal ({ocr_err_msg}). " if ocr_err_msg else "")
                + "Verifikasi dan koreksi data di bawah sebelum menyimpan."
            )
            return {
                "ok": True,
                "receipts": [parsed],
                "engine_ranking": ["rule-engine-v1"],
                "ai_powered": True,
                "provider": "rules",
            }

        # Check if Ollama returned OCR-sentinel (rules path via _ai_chat_vision)
        try:
            sentinel = json.loads(raw)
            if "_rule_ocr_text" in sentinel:
                eng = _load_rule_engine()
                if eng:
                    parsed = (_load_receipt_parser() or eng).rule_based_receipt_parse(sentinel["_rule_ocr_text"])
                    parsed["engine"] = info["model"]
                    return {
                        "ok": True,
                        "receipts": [parsed],
                        "engine_ranking": [info["model"]],
                        "ai_powered": True,
                        "provider": info["provider"],
                    }
        except (json.JSONDecodeError, TypeError):
            pass

        raw = _strip_json_fences(raw)
        parsed = json.loads(raw)

        merchant_name = str(parsed.get("merchant") or parsed.get("merchant_name") or "Unknown").strip()
        date_str      = str(parsed.get("date") or parsed.get("transaction_date") or datetime.now().strftime("%Y-%m-%d")).strip()
        notes_str     = str(parsed.get("notes") or "").strip()

        # Item list extraction & price cleaning
        items = []
        raw_items = parsed.get("items") or []
        items_total_sum = 0.0
        if isinstance(raw_items, list):
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                i_name = str(item.get("name") or "").strip()
                if not i_name:
                    continue
                i_qty   = _clean_idr_amount(item.get("qty", 1)) or 1.0
                i_price = _clean_idr_amount(item.get("unit_price") or item.get("price") or 0)
                i_tot   = _clean_idr_amount(item.get("total")) or (i_qty * i_price)
                items_total_sum += i_tot
                items.append({
                    "name": i_name,
                    "qty": i_qty,
                    "unit_price": i_price,
                    "total": i_tot
                })

        # Total amount cleaning
        total_amt = _clean_idr_amount(parsed.get("amount") or parsed.get("total_amount") or 0)
        if total_amt <= 0 and items_total_sum > 0:
            total_amt = items_total_sum

        # Document type detection
        doc_type, doc_label = detect_document_type(f"{merchant_name} {notes_str} {parsed.get('category','')}")

        receipt = {
            "merchant_name":    merchant_name,
            "transaction_date": date_str[:10],
            "total_amount":     total_amt,
            "currency":         parsed.get("currency", "IDR"),
            "payment_method":   parsed.get("payment_method", "cash"),
            "transaction_type": parsed.get("type") or parsed.get("transaction_type") or "expense",
            "category":         parsed.get("category", "other"),
            "confidence":       float(parsed.get("confidence", 0.90)),
            "engine":           info["model"],
            "document_type":    doc_type,
            "doc_type_label":   doc_label,
            "items":            items,
            "notes":            notes_str,
            "ai_analysis":      parsed.get("ai_analysis", ""),
        }
        # Apply merchant memory â€” overrides AI category if merchant is known
        mm = _get_merchant_memory()
        if mm and hasattr(mm, "enrich_receipt_category"):
            receipt = mm.enrich_receipt_category(receipt)
        return {
            "ok": True,
            "receipts": [receipt],
            "engine_ranking": [info["model"]],
            "ai_powered": True,
            "provider": info["provider"],
        }

    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"Format JSON tidak valid: {e}. Raw: {raw[:200]}", "receipts": []}
    except HTTPException:
        raise
    except Exception:
        logger.exception("[scan-ai] Unhandled AI scan error")
        return {"ok": False, "error": "AI scan failed. Please try again.", "receipts": []}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── NL Transaction Parser (Phase 3) ─────────────────────────────────────────────

_NL_PARSE_SYSTEM = """Kamu adalah asisten pencatat keuangan pribadi. Pengguna mengetik
transaksi dalam bahasa sehari-hari (Indonesia/Inggris). Ekstrak datanya dan jawab
HANYA dengan JSON valid tanpa teks lain, dengan format:

{"type": "expense"|"income"|"transfer", "amount": <angka>, "category": "<nama kategori>",
 "merchant_name": "<nama merchant/toko>", "description": "<deskripsi singkat>",
 "transaction_date": "YYYY-MM-DD", "confidence": <0.0-1.0>}

Untuk transfer antar rekening (misal "transfer 500rb dari BCA ke Jago",
"BCA ke Jago 1jt", "pindahkan 2jt ke Jago dari BCA"), set type menjadi
"transfer" dan tambahkan field berikut:

{"from_account": "<nama rekening asal>", "to_account": "<nama rekening tujuan>"}

Jangan menebak rekening: hanya isi from_account/to_account jika pengguna
menyebut keduanya secara eksplisit. Untuk transfer, category = "Transfer".

Contoh kategori pengeluaran: Food, Transport, Housing, Entertainment, Health,
Shopping, Education, Investment, Other.
Contoh kategori pemasukan: Salary, Freelance, Side Hustle, Transfer, Bonus, Gift, Other.
Gunakan tanggal hari ini jika tidak disebutkan. Amount tanpa pemisah ribuan."""


_CATEGORY_MAP = {
    "food": "Food", "transport": "Transport", "housing": "Housing",
    "entertainment": "Entertainment", "health": "Health", "shopping": "Shopping",
    "education": "Education", "investment": "Investment", "other": "Other",
    "salary": "Salary", "freelance": "Freelance", "side-hustle": "Side Hustle",
    "transfer": "Transfer", "bonus": "Bonus", "gift": "Gift",
    "food & drink": "Food", "makanan": "Food", "minuman": "Food",
}


def _map_nl_category(raw: Any, tx_type: str) -> str:
    key = str(raw or "").strip().lower()
    if key in _CATEGORY_MAP:
        return _CATEGORY_MAP[key]
    if tx_type == "income":
        return "Other" if not key else str(raw).strip()
    return "Other" if not key else str(raw).strip()


def _normalize_nl_draft(parsed: dict, default_type: str = "expense") -> dict:
    """Normalize an AI/rule parsed dict into the confirmation-engine draft shape."""
    tx_type = str(parsed.get("type") or parsed.get("transaction_type") or default_type).strip().lower()
    if tx_type not in ("expense", "income", "transfer"):
        tx_type = default_type

    amount = parsed.get("amount")
    if amount is None:
        amount = parsed.get("total_amount")
    if isinstance(amount, str):
        amount = _clean_idr_amount(amount)
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        amount = 0.0

    merchant = str(parsed.get("merchant_name") or parsed.get("merchant") or "").strip()
    description = str(
        parsed.get("description") or parsed.get("notes") or merchant
    ).strip()

    raw_date = str(parsed.get("transaction_date") or parsed.get("date") or "").strip()
    date_str = raw_date.split("T")[0].split(" ")[0] if raw_date else date.today().isoformat()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        date_str = date.today().isoformat()

    try:
        confidence = float(parsed.get("confidence") or 0.9)
    except (TypeError, ValueError):
        confidence = 0.9

    return {
        "type": tx_type,
        "amount": round(amount, 2),
        "total_amount": round(amount, 2),
        "category": _map_nl_category(parsed.get("category"), tx_type),
        "merchant_name": merchant,
        "description": description,
        "transaction_date": date_str,
        "date": date_str,
        "confidence": confidence,
        "from_account": str(parsed.get("from_account") or parsed.get("from") or "").strip()
        if tx_type == "transfer" else "",
        "to_account": str(parsed.get("to_account") or parsed.get("to") or "").strip()
        if tx_type == "transfer" else "",
    }


_TRANSFER_KEYWORDS = (
    "transfer", "pindah buku", "pindahkan", "pindah", "top up", "topup",
    "mutasi", "kirim uang", "kirimkan",
)

_TRANSFER_KEYWORD_WORDS = (
    "transfer", "pindahkan", "pindah buku", "pindah", "top up", "topup",
    "mutasi", "kirim uang", "kirimkan", "kirim",
)

_TRANSFER_FROM_TO_RE = re.compile(
    r"(?:dari|from)\s+([^\d,;]+?)\s+(?:ke|kepada|to)\s+([^\d,;]+?)(?:\s|$)"
)
_TRANSFER_ARROW_RE = re.compile(
    r"([^\d,;]+?)\s*(?:→|->|=>)\s*([^\d,;]+?)(?:\s|$)"
)
_TRANSFER_KE_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9 .\-&]{1,40}?)\s+(?:ke|kepada|to)\s+"
    r"([A-Za-z][A-Za-z0-9 .\-&]{1,40})(?:\s|$)"
)
_TRANSFER_AMOUNT_STRIP_RE = re.compile(r"(?i)(?:rp\s*)?\d[\d.,]*\s*(?:k|rb|jt|juta|ribu|ratus)?\s*")


def _strip_account_noise(name: str) -> str:
    """Trim filler/prefix words so account names survive name-matching later."""
    n = re.sub(r"\s+", " ", name).strip().strip(".,;:!?()[]'\"")
    low = n.lower()
    for prefix in ("rekening ", "kartu ", "akun ", "dompet ", "bank "):
        if low.startswith(prefix):
            n = n[len(prefix):].strip()
            low = n.lower()
    for kw in _TRANSFER_KEYWORD_WORDS:
        if low.startswith(kw):
            n = n[len(kw):].strip()
            break
    return n


def _known_ledger_accounts() -> List[str]:
    """Active account names from the canonical ledger, or [] when unavailable."""
    try:
        from packages.api.backend.finance import ledger_engine
        from packages.core.infrastructure.config import Config
        return [
            a["name"]
            for a in ledger_engine.list_accounts(
                Config.get_db_path("finance"), include_inactive=True
            )
        ]
    except Exception:
        return []


def _detect_rule_transfer(text: str, known_accounts: Optional[List[str]] = None):
    """Detect an explicit account-to-account transfer mention in free text.

    Returns (from_account, to_account) or None. Conservative by design: a
    transfer is only classified when there is an explicit marker (transfer
    keyword, "dari ... ke ...", or an arrow) — or, for the bare "X ke Y"
    form, when both names already exist in the ledger — so ordinary
    sentences like "jajan 50k di BCA" never become transfers.
    """
    low = (text or "").strip()
    if not low:
        return None
    low_lower = low.lower()
    has_keyword = any(kw in low_lower for kw in _TRANSFER_KEYWORDS)
    core = _TRANSFER_AMOUNT_STRIP_RE.sub(" ", low)
    core = re.sub(r"\s+", " ", core).strip()

    matched = _TRANSFER_FROM_TO_RE.search(core) or _TRANSFER_ARROW_RE.search(core)
    is_plain_ke = False
    if not matched and has_keyword:
        matched = _TRANSFER_KE_RE.search(core)
    elif not matched and "dari" not in low_lower:
        candidate = _TRANSFER_KE_RE.search(core)
        if candidate:
            matched = candidate
            is_plain_ke = True
    if not matched:
        return None

    from_acc = _strip_account_noise(matched.group(1))
    to_acc = _strip_account_noise(matched.group(2))
    if "dari" in to_acc.lower():
        # Reversed phrasing: "ke Jago dari BCA"
        parts = re.split(r"\s+dari\s+", to_acc, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            if not from_acc:
                from_acc = parts[1].strip()
            to_acc = parts[0].strip()
    if not from_acc or not to_acc or from_acc.lower() == to_acc.lower():
        return None

    if is_plain_ke:
        known = [str(k).lower() for k in (known_accounts or [])]
        if not known:
            return None

        def _known_match(name: str) -> bool:
            n = name.lower()
            return any(n == k or n in k or k in n for k in known)

        if not (_known_match(from_acc) and _known_match(to_acc)):
            return None
    return from_acc, to_acc


def _rule_parse_nl(text: str, default_type: str = "expense") -> dict:
    """Rule-based fallback: amount + keyword category + today's date."""
    from packages.api.telegram_handler import detect_category, parse_amount

    amount = None
    for token in re.split(r"\s+", text):
        candidate = parse_amount(token)
        if candidate:
            amount = candidate
            break
    if amount is None:
        amount = parse_amount(text) or 0.0

    transfer = _detect_rule_transfer(text, known_accounts=_known_ledger_accounts())
    if transfer and float(amount) > 0:
        from_account, to_account = transfer
        description = re.sub(r"\s+", " ", text).strip()
        return {
            "type": "transfer",
            "amount": round(float(amount), 2),
            "total_amount": round(float(amount), 2),
            "category": "Transfer",
            "from_account": from_account,
            "to_account": to_account,
            "merchant_name": "",
            "description": description[:120],
            "transaction_date": date.today().isoformat(),
            "date": date.today().isoformat(),
            "confidence": 0.6,
        }

    category_key = detect_category(text, default_type)
    category = _map_nl_category(category_key, default_type)
    description = re.sub(r"\s+", " ", text).strip()
    return {
        "type": default_type,
        "amount": round(float(amount), 2),
        "total_amount": round(float(amount), 2),
        "category": category,
        "merchant_name": description[:60],
        "description": description,
        "transaction_date": date.today().isoformat(),
        "date": date.today().isoformat(),
        "confidence": 0.6,
    }


def _validate_nl_draft(draft: dict) -> dict:
    """Wire the CompositeValidator chain (Amount/Date/Merchant) into parse -> draft."""
    from packages.core.application.receipt_reader.interfaces import (
        Money,
        PaymentMethod,
        ReceiptData,
        TransactionType,
    )
    from packages.core.application.receipt_reader.validator import CompositeValidator

    try:
        tx_type = TransactionType(draft.get("type", "expense"))
    except ValueError:
        tx_type = TransactionType.EXPENSE
    try:
        tx_date = datetime.strptime(str(draft["transaction_date"]), "%Y-%m-%d")
    except (KeyError, ValueError):
        tx_date = datetime.now()

    receipt = ReceiptData(
        merchant_name=draft.get("merchant_name") or "",
        transaction_date=tx_date,
        total_amount=Money(float(draft.get("amount") or 0)),
        payment_method=PaymentMethod.E_WALLET,
        transaction_type=tx_type,
        confidence_score=float(draft.get("confidence") or 0),
    )
    is_valid, errors = CompositeValidator().validate(receipt)
    return {"is_valid": is_valid, "errors": errors}


class ParseTextBody(BaseModel):
    text: str
    transaction_type: Optional[str] = None


def parse_transaction_text(text: str, transaction_type: Optional[str] = None) -> dict:
    """
    Phase 3 — Natural-language -> validated draft (core logic).

    Parses free-form transaction text (e.g. "beli kopi 25rb" / "gaji bulan agustus
    7,5jt") into a structured draft via the LLM, falling back to the rule engine,
    then validates it through the receipt CompositeValidator chain.
    """
    text = (text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text is required")
    default_type = (transaction_type or "").strip().lower()
    if default_type not in ("expense", "income"):
        default_type = "expense"

    info = _detect_provider()
    engine = info["provider"]
    draft = None
    raw = ""

    if info["provider"] not in ("none", "rules"):
        try:
            raw = _ai_chat(
                _NL_PARSE_SYSTEM,
                f"Transaksi: \"{text}\"",
                max_tokens=300,
            )
            raw = _strip_json_fences(raw)
            raw = _repair_truncated_json(raw)
            parsed = json.loads(raw)
            draft = _normalize_nl_draft(parsed, default_type)
            engine = info["model"]
        except HTTPException:
            logger.warning("[parse-text] LLM provider unavailable; falling back to rules")
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("[parse-text] LLM output unparsable; falling back to rules")

    if draft is None:
        try:
            draft = _rule_parse_nl(text, default_type)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[parse-text] Rule parse failed")
            return {"ok": False, "error": f"Parse failed: {exc}", "ai_powered": False}

    validation = _validate_nl_draft(draft)
    return {
        "ok": True,
        "draft": draft,
        "validation": validation,
        "engine": engine,
        "ai_powered": info["provider"] != "rules",
        "provider": info["provider"],
    }


@router.post("/api/ai/parse-text", dependencies=[Depends(require_scope("write"))])
async def parse_text_transaction(body: ParseTextBody):
    # parse_transaction_text sinkron (bisa manggil LLM dgn timeout panjang) —
    # jangan jalankan di event loop.
    return await asyncio.to_thread(parse_transaction_text, body.text, body.transaction_type)


@router.get("/api/ai/insights")
async def get_ai_insights():
    """
    AI-powered behavioral finance analysis.
    Provider priority: Claude API â†’ Ollama â†’ Rule-based engine (always available).
    Returns structured JSON displayed in AIInsightPanel.
    Rule-based output is bilingual (ID+EN) and schema-compatible with LLM output.
    """
    info = _detect_provider()
    now = datetime.now()

    # â”€â”€ Rule-based path (pure Python, zero dependencies) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if info["provider"] == "rules":
        try:
            eng = _load_rule_engine()
            if not eng:
                logger.error("Rule engine not available")
                raise HTTPException(503, "Rule engine tidak tersedia.")

            # Reuse the canonical aggregator: it resolves the report month
            # with fallback and excludes transfer income (consistent with the
            # dashboard and with the LLM path).
            d = _gather_financial_data(now)
            budget_limits = {r["category"]: r["limit_amt"] for r in d["budget_rows"]}

            insights = eng.rule_based_insights(
                total_income=d["total_inc"],
                total_expense=d["total_exp"],
                income_prev=d["inc_prev_total"],
                expense_prev=d["exp_prev_total"],
                by_category=d["by_cat"],
                budget_limits=budget_limits,
                emergency_fund=d["emergency_fund"],
                month_label=d["month_label"],
                fbs_score=d["fbs_score"],
                fbs_grade=d["fbs_grade"],
                impulse_index=d["impulse_index"],
                income_sources=d["income_sources"],
                profile_name=d.get("profile_name", ""),
                profile_type=d.get("profile_type", ""),
                transfer_income=d.get("transfer_income", 0.0),
                anomalies=d.get("anomalies", []),
                goals=d.get("goals", []),
            )
            insights["generated_at"] = now.isoformat()
            insights["data_period"]  = d["month_label"]
            insights["ai_powered"]   = True
            insights["provider"]     = "rules"
            insights["model"]        = "rule-engine-v1"
            if d["fallback_applied"]:
                insights["warning"] = (
                    f"Bulan berjalan belum ada data - analisis memakai bulan "
                    f"terakhir yang berisi data: {d['month_label']}."
                )
            return insights

        except HTTPException:
            raise
        except Exception:
            logger.exception("[ai-insights] Rule engine failed")
            return {"ok": False, "error": "Insight generation failed.", "ai_powered": True, "provider": "rules"}

    # â”€â”€ LLM path (Claude or Ollama) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # provider seharusnya tidak pernah "none" lagi (sudah fallback ke rules di _detect_provider)
    # tapi jaga-jaga:
    if info["provider"] == "none":
        return {
            "ok": False,
            "error": info["reason"],
            "ai_powered": False,
            "provider": "none",
            "generated_at": now.isoformat(),
        }

    d = _gather_financial_data(now)
    data_context = _format_financial_context(d)
    sys_prompt   = _insights_system_for(info["model"])
    user_suffix  = "Jawab dalam JSON sesuai format." if sys_prompt is _INSIGHTS_SYSTEM_SMALL else "Berikan analisis mendalam dan rekomendasi personal berdasarkan data di atas."
    raw = ""
    try:
        raw = await asyncio.to_thread(
            _ai_chat,
            sys_prompt,
            f"{data_context}\n\n{user_suffix}",
            max_tokens=_insights_tokens_for(info["model"], 2048),
        )
        raw = _strip_json_fences(raw)
        raw = _repair_truncated_json(raw)
        insights = json.loads(raw)
        insights["generated_at"] = now.isoformat()
        insights["data_period"]  = d["month_label"]
        if d["fallback_applied"]:
            insights["warning"] = (
                f"Bulan berjalan belum ada data - analisis memakai bulan "
                f"terakhir yang berisi data: {d['month_label']}."
            )
        insights["ai_powered"]   = True
        insights["provider"]     = info["provider"]
        insights["model"]        = info["model"]
        return insights

    except json.JSONDecodeError as e:
        return {
            "ok": False,
            "error": f"Format respons tidak valid: {e}. Raw: {raw[:300]}",
            "ai_powered": True,
            "provider": info["provider"],
        }
    except HTTPException as http_exc:
        # LLM gagal â€” fallback ke rule engine (DRY: reuse _gather_financial_data)
        try:
            eng = _load_rule_engine()
            if eng:
                d = _gather_financial_data(now)
                budget_limits = {r["category"]: r["limit_amt"] for r in d["budget_rows"]}
                insights = eng.rule_based_insights(
                    total_income=d["total_inc"],
                    total_expense=d["total_exp"],
                    income_prev=d["inc_prev_total"],
                    expense_prev=d["exp_prev_total"],
                    by_category=d["by_cat"],
                    budget_limits=budget_limits,
                    emergency_fund=d["emergency_fund"],
                    month_label=d["month_label"],
                    income_sources=d["income_sources"],
                    profile_name=d.get("profile_name", ""),
                    profile_type=d.get("profile_type", ""),
                    transfer_income=d.get("transfer_income", 0.0),
                    anomalies=d.get("anomalies", []),
                    goals=d.get("goals", []),
                )
                insights["generated_at"] = now.isoformat()
                insights["data_period"]  = d["month_label"]
                insights["ai_powered"]   = True
                insights["provider"]     = "rules"
                insights["model"]        = "rule-engine-v1"
                insights["warning"]      = f"AI provider gagal ({http_exc.detail}) - tampil rule-based."
                return insights
        except Exception:
            logger.exception("Error while applying AI post-processor")
            pass
        raise http_exc
    except Exception:
        logger.exception("[ai-insights] Unhandled insight error")
        return {"ok": False, "error": "Insight processing failed.", "ai_powered": True, "provider": info.get("provider", "?")}


@router.get("/api/ai/insights/stream")
async def stream_ai_insights():
    """
    SSE endpoint â€” streams Ollama token-by-token so the UI shows live progress
    instead of freezing for 30-60 s.

    Events emitted:
      data: {"type":"token",  "text":"â€¦"}      â€” each Ollama token chunk
      data: {"type":"done",   "result":{â€¦}}    â€” final parsed JSON insights
      data: {"type":"error",  "message":"â€¦"}   â€” any failure
      data: {"type":"status", "message":"â€¦"}   â€” progress milestone (model start, etc.)

    Falls back to rule engine (non-streaming) if provider is not Ollama.
    """
    import asyncio

    info = _detect_provider()
    now = datetime.now()

    async def _generate():
        # â”€â”€ Non-Ollama providers: Claude or rules â€” just return JSON as single done event
        if info["provider"] != "ollama":
            try:
                status_msg = json.dumps({"type": "status", "message": f"Menganalisis dengan {info['provider']}..."})
                yield f"data: {status_msg}\n\n"
                # Run blocking call in thread so we don't block the event loop
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: _blocking_insights(info, now))
                done_msg = json.dumps({"type": "done", "result": result})
                yield f"data: {done_msg}\n\n"
            except Exception as ex:
                err_msg = json.dumps({"type": "error", "message": str(ex)})
                yield f"data: {err_msg}\n\n"
            return

        # â”€â”€ Ollama streaming path â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        d = _gather_financial_data(now)
        data_context = _format_financial_context(d)
        sys_prompt   = _insights_system_for(info["model"])
        user_suffix  = "Jawab dalam JSON sesuai format." if sys_prompt is _INSIGHTS_SYSTEM_SMALL else "Berikan analisis mendalam dan rekomendasi personal berdasarkan data di atas."
        user_prompt  = f"{data_context}\n\n{user_suffix}"
        capped = _ollama_token_cap(info["model"], _insights_tokens_for(info["model"], 512))

        payload = json.dumps(
            {
                "model": info["model"],
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": True,
                "options": {"num_predict": capped, "temperature": 0.3},
            }
        ).encode()

        load_msg = json.dumps({"type": "status", "message": f"Memuat {info['model']}â€¦"})
        yield f"data: {load_msg}\n\n"
        logger.info(f"[ollama/stream] â†’ {info['model']}  num_predict={capped}")

        loop = asyncio.get_event_loop()

        def _do_stream():
            """Blocking: collects all Ollama NDJSON stream lines. Raises on HTTP error."""
            req = _urlreq.Request(
                f"{_ollama_base()}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            chunks = []
            try:
                with _urlreq.urlopen(req, timeout=45) as resp:
                    for raw_line in resp:
                        line = raw_line.decode().strip()
                        if line:
                            chunks.append(line)
            except _urlerr.HTTPError as he:
                body = ""
                try: body = he.read().decode()[:200]
                except Exception: body = '(Gagal membaca body error)'
                logger.exception("Error while generating AI response")
                raise RuntimeError(f"Ollama HTTP {he.code}: {body}")
            except _urlerr.URLError as ue:
                raise RuntimeError(f"Ollama tidak dapat dihubungi: {ue.reason}")
            return chunks

        try:
            raw_lines = await loop.run_in_executor(None, _do_stream)
        except Exception as ex:
            logger.warning(f"[ollama/stream] request failed: {ex} â€” falling back to rule engine")
            # Graceful degradation: try rule engine before returning error
            try:
                eng = _load_rule_engine()
                if eng:
                    d = _gather_financial_data(now)
                    budget_limits = {r["category"]: r["limit_amt"] for r in d["budget_rows"]}
                    fallback_insights = eng.rule_based_insights(
                        total_income=d["total_inc"],
                        total_expense=d["total_exp"],
                        income_prev=d["inc_prev_total"],
                        expense_prev=d["exp_prev_total"],
                        by_category=d["by_cat"],
                        budget_limits=budget_limits,
                        emergency_fund=d.get("emergency_fund", 0),
                        month_label=d["month_label"],
                        profile_name=d.get("profile_name", ""),
                        profile_type=d.get("profile_type", ""),
                        transfer_income=d.get("transfer_income", 0.0),
                        anomalies=d.get("anomalies", []),
                        goals=d.get("goals", []),
                    )
                    fallback_insights.update({
                        "generated_at": now.isoformat(), "data_period": d["month_label"],
                        "ai_powered": True, "provider": "rules", "model": "rule-engine-v1",
                        "warning": f"Ollama gagal ({ex}) - ditampilkan Rule Engine.",
                    })
                    done_fb = json.dumps({"type": "done", "result": fallback_insights})
                    yield f"data: {done_fb}\n\n"
                    return
            except Exception as fb_ex:
                logger.warning(f"[ollama/stream] rule-engine fallback also failed: {fb_ex}")
            err_msg2 = json.dumps({"type": "error", "message": str(ex)})
            yield f"data: {err_msg2}\n\n"
            return

        # Replay token chunks to client as SSE events, then parse final JSON
        full_text = []
        for line in raw_lines:
            try:
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    full_text.append(token)
                    tok_msg = json.dumps({"type": "token", "text": token})
                    yield f"data: {tok_msg}\n\n"
            except Exception:
                logger.exception("Error while flushing AI response cache")
                pass

        combined = "".join(full_text).strip()
        logger.info(f"[ollama/stream] â† done  len={len(combined)}")

        # Parse and return structured insights
        try:
            cleaned = _strip_json_fences(combined)
            cleaned = _repair_truncated_json(cleaned)
            insights = json.loads(cleaned)
            insights["generated_at"] = now.isoformat()
            insights["data_period"]  = d["month_label"]
            if d["fallback_applied"]:
                insights["warning"] = (
                    f"Bulan berjalan belum ada data - analisis memakai bulan "
                    f"terakhir yang berisi data: {d['month_label']}."
                )
            insights["ai_powered"]   = True
            insights["provider"]     = info["provider"]
            insights["model"]        = info["model"]
            done_msg2 = json.dumps({"type": "done", "result": insights})
            yield f"data: {done_msg2}\n\n"
        except json.JSONDecodeError:
            parse_err_msg = json.dumps({"type": "error", "message": f"JSON parse gagal. Raw: {combined[:200]}"})
            yield f"data: {parse_err_msg}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering if proxied
        },
    )


def _blocking_insights(info: dict, now) -> dict:
    """Synchronous helper: run Claude/rules insights (called via run_in_executor)."""
    d = _gather_financial_data(now)
    data_context = _format_financial_context(d)
    sys_prompt   = _insights_system_for(info["model"])
    user_suffix  = "Jawab dalam JSON sesuai format." if sys_prompt is _INSIGHTS_SYSTEM_SMALL else "Berikan analisis mendalam dan rekomendasi personal berdasarkan data di atas."
    raw = _ai_chat(
        sys_prompt,
        f"{data_context}\n\n{user_suffix}",
        max_tokens=_insights_tokens_for(info["model"], 512),
    )
    raw = _strip_json_fences(raw)
    raw = _repair_truncated_json(raw)
    insights = json.loads(raw)
    insights["generated_at"] = now.isoformat()
    insights["data_period"]  = d["month_label"]
    if d["fallback_applied"]:
        insights["warning"] = (
            f"Bulan berjalan belum ada data - analisis memakai bulan "
            f"terakhir yang berisi data: {d['month_label']}."
        )
    insights["ai_powered"]   = True
    insights["provider"]     = info["provider"]
    insights["model"]        = info["model"]
    return insights
