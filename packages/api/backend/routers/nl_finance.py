"""
backend/routers/nl_finance.py — NL Finance Query API (Phase 11)
================================================================
Controlled endpoint for free-form finance questions: intent detection →
deterministic backend computation → explanation (AI explains, backend
computes). An LLM (or any caller) may classify the intent and pass
intent+params explicitly; the numbers always come from the ledger-backed
Phase 5-10 services, never from the model.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from packages.api.backend.finance.nl_intent_service import (
    NLIntentError,
    detect_finance_intent,
    execute_finance_intent,
)
from packages.api.backend.security.core import require_scope
from packages.core.infrastructure.config import Config

router = APIRouter()
logger = logging.getLogger(__name__)


class NLFinanceRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500, description="Free-form finance question in Indonesian/English")
    intent: str | None = None
    params: dict | None = None


@router.post("/api/nl/finance", dependencies=[Depends(require_scope("read"))])
def nl_finance_query(body: NLFinanceRequest):
    try:
        result = execute_finance_intent(
            Config.get_db_path("finance"),
            budget_db=Config.get_db_path("budget"),
            text=body.text,
            intent=body.intent,
            params=body.params,
        )
    except NLIntentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:  # noqa: BLE001
        logger.exception("NL finance intent computation failed")
        raise HTTPException(status_code=500, detail=f"NL finance failed: {exc}") from None

    if result is None:
        return {
            "ok": False,
            "intent": None,
            "explanation": "Pertanyaan tidak dikenali sebagai intent keuangan. "
                           "Coba: saldo, aman belanja, proyeksi, laporan, budget, transaksi terakhir.",
            "data": None,
        }
    return {"ok": True, **result}


@router.get("/api/nl/finance/intents", dependencies=[Depends(require_scope("read"))])
def nl_finance_intents():
    return {
        "ok": True,
        "intents": [
            {"intent": "GET_BALANCE", "examples": ["berapa saldo saya", "cek saldo"]},
            {"intent": "GET_SAFE_TO_SPEND", "examples": ["aman belanja berapa", "sisa aman 7 hari"]},
            {"intent": "GET_FORECAST", "examples": ["proyeksi bulan ini", "prediksi 14 hari"]},
            {"intent": "GET_REPORT", "examples": ["laporan minggu ini", "laporan bulan ini"]},
            {"intent": "GET_BUDGET_STATUS", "examples": ["sisa budget bulan ini", "status budget"]},
            {"intent": "GET_ANOMALIES", "examples": ["anomali", "ada kejanggalan pengeluaran?"]},
            {"intent": "GET_INSIGHTS", "examples": ["wawasan keuangan", "ringkasan keuangan"]},
            {"intent": "GET_HEALTH_SCORE", "examples": ["skor kesehatan keuangan", "sehatkah saya?"]},
            {"intent": "GET_NET_WORTH", "examples": ["berapa kekayaan saya", "net worth"]},
            {"intent": "GET_RECENT", "examples": ["transaksi terakhir", "pengeluaran terakhir 3"]},
        ],
    }


@router.get("/api/nl/finance/detect", dependencies=[Depends(require_scope("read"))])
def nl_finance_detect(q: str = ""):
    """Pure intent classification without computing anything (for callers
    that want to preview the mapping before executing)."""
    return {"ok": True, **({"detected": detect_finance_intent(q)} if q else {"detected": None})}
