#!/usr/bin/env python3
"""
Finance Tracker — Telegram Bot Handler
========================================
Handles incoming Telegram messages from n8n webhook.
Supports receipt photo scanning with interactive inline keyboard confirmation.
For text messages: sends an auto-response guide (does not save/classify).

Architecture:
  n8n Telegram Trigger
      └─ If Photo = TRUE  → n8n downloads photo, scans via OCR, and POSTs result to /telegram/receipt_pending
      └─ If Photo = FALSE → n8n POSTs raw update directly to /telegram/webhook
"""

import hmac
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── Env ─────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
load_dotenv(_HERE / ".env")

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
TELEGRAM_API_BASE: str = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

logger = logging.getLogger("api.telegram_bot")

# Navigation state for the confirmation queue (drafts live in the persistent
# store via packages/api/backend/finance/confirmation_engine.py — Phase 3).
# Schema: { chat_id: { "tokens": [str, ...], "current_index": int } }
PENDING_RECEIPTS: Dict[int, Dict[str, Any]] = {}

# ── DB Helpers ──────────────────────────────────────────────────────────────
try:
    from packages.api.backend.routers.deps import _check_and_apply_reward_unlocks, _db, _execute
except ImportError:
    _db = None
    _execute = None
    _check_and_apply_reward_unlocks = None
    logger.warning("Could not import database dependencies. DB operations will be stubbed.")

# ── Confirmation Store Helpers (Phase 3) ─────────────────────────────────────
# Drafts live in the persistent confirmation store; the in-memory dict only
# tracks queue navigation (raw one-time tokens are never persisted).

def _chat_db() -> str:
    from packages.core.infrastructure.config import Config
    return Config.get_db_path("chat")


def _ledger_db() -> str:
    from packages.core.infrastructure.config import Config
    return Config.get_db_path("finance")


def _ce():
    from packages.api.backend.finance import confirmation_engine
    return confirmation_engine


def _ensure_chat_bound(chat_id: int) -> None:
    """Per-chat auth: auto-bind an unbound chat to the active profile."""
    ce = _ce()
    if not ce.get_binding(_chat_db(), chat_id):
        ce.bind_chat(_chat_db(), chat_id)


def _active_draft(chat_id: int) -> Optional[Dict[str, Any]]:
    """Return {token, row} for the current queue position, or None."""
    session = PENDING_RECEIPTS.get(chat_id)
    if not session:
        return None
    tokens = session.get("tokens") or []
    idx = session.get("current_index", 0)
    if idx >= len(tokens):
        return None
    try:
        row = _ce().get_draft(_chat_db(), tokens[idx])
    except Exception:
        return None
    return {"token": tokens[idx], "row": row}


def _draft_receipt(chat_id: int) -> Optional[Dict[str, Any]]:
    """Draft dict of the currently active queue item, or None."""
    active = _active_draft(chat_id)
    return active["row"]["draft"] if active else None


_KNOWN_COMMANDS = frozenset({
    "/start", "/help", "help", "halo", "hai",
    "/summary", "summary", "laporan", "laporan bulanan", "bulan ini",
    "/daily", "daily", "hari ini", "laporan hari ini", "laporan harian",
    "laporan minggu ini", "report minggu ini", "minggu ini",
    "laporan bulan ini", "report bulan ini", "report hari ini",
    "/saldo", "saldo", "rekening", "pocket", "pockets",
    "/budget", "budget", "limit", "sisa budget",
    "forecast", "prediksi", "proyeksi",
    "safetospend", "safe to spend", "aman belanja", "sisa aman",
    "anomalies", "anomali", "anomaly", "kejanggalan",
    "insights", "wawasan",
    "health", "healthscore", "health score", "skor kesehatan", "sehat",
    "networth", "net worth", "kekayaan",
})

_EXPLICIT_TX_RE = [
    re.compile(r"^(?:tambah\s+)?pengeluaran\s+\S+\s+.+", re.IGNORECASE),
    re.compile(r"^(?:tambah\s+)?pemasukan\s+\S+\s+.+", re.IGNORECASE),
    re.compile(r"^/expense\s+\S+\s+.+", re.IGNORECASE),
    re.compile(r"^/income\s+\S+\s+.+", re.IGNORECASE),
    re.compile(r"^add\s+expense\s+\S+\s+.+", re.IGNORECASE),
    re.compile(r"^add\s+income\s+\S+\s+.+", re.IGNORECASE),
]


_REPORT_RE = re.compile(
    r"^(?:/report\b|report\b|/weekly\b|weekly\b|/monthly\b|monthly\b)", re.IGNORECASE
)

_FORECAST_RE = re.compile(r"^forecast(?:\s+\d+)?$", re.IGNORECASE)

_SAFE_SPEND_RE = re.compile(r"^safetospend(?:\s+\d+)?(?:\s+\d+)?$", re.IGNORECASE)


def _is_explicit_command(text: str) -> bool:
    """True for help/report/forecast/safe-to-spend commands and structured add-tx prefixes."""
    low = text.strip().lower()
    if low in _KNOWN_COMMANDS:
        return True
    if _REPORT_RE.match(text):
        return True
    if _FORECAST_RE.match(text):
        return True
    if _SAFE_SPEND_RE.match(text):
        return True
    return any(p.match(text) for p in _EXPLICIT_TX_RE)


def _handle_finance_intent(text: str) -> Optional[str]:
    """Resolve a free-form finance question to a deterministic, ledger-backed
    answer (Phase 11). Returns None when the text is not a finance intent, so
    the caller falls through to the add-transaction draft flow."""
    try:
        from packages.api.backend.finance.nl_intent_service import (
            execute_finance_intent,
            format_intent_reply,
        )
        from packages.core.infrastructure.config import Config
        result = execute_finance_intent(
            Config.get_db_path("finance"),
            budget_db=Config.get_db_path("budget"),
            text=text,
        )
    except Exception:
        logger.exception("[nl-intent] finance intent computation failed")
        return None
    if result is None:
        return None
    return format_intent_reply(result)


def _parse_nl_text(text: str) -> Optional[Dict[str, Any]]:
    """Free-form text -> draft via the shared parse pipeline (LLM + rule fallback)."""
    from packages.api.backend.routers.ai import parse_transaction_text
    try:
        result = parse_transaction_text(text, None)
    except Exception:
        logger.exception("[parse-nl] parse pipeline failed")
        return None
    return result.get("draft") if result.get("ok") else None

# ── Telegram API Helpers ─────────────────────────────────────────────────────

async def _tg_call(method: str, payload: dict) -> dict:
    """Make an async call to the Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping Telegram call.")
        return {}
    url = f"{TELEGRAM_API_BASE}/{method}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


async def send_message(chat_id: int | str, text: str, parse_mode: str = "HTML", reply_markup: Optional[dict] = None) -> dict:
    """Send a text message with optional reply markup."""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _tg_call("sendMessage", payload)


async def edit_message(chat_id: int | str, message_id: int, text: str, parse_mode: str = "HTML", reply_markup: Optional[dict] = None) -> dict:
    """Edit an existing message with optional reply markup."""
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return await _tg_call("editMessageText", payload)


async def answer_callback_query(callback_query_id: str, text: Optional[str] = None, show_alert: bool = False) -> dict:
    """Acknowledge receipt of a callback query."""
    payload = {
        "callback_query_id": callback_query_id,
    }
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert
    return await _tg_call("answerCallbackQuery", payload)


async def send_chat_action(chat_id: int | str, action: str = "typing") -> dict:
    """Show typing/upload indicator in Telegram chat."""
    return await _tg_call("sendChatAction", {
        "chat_id": chat_id,
        "action": action,
    })

# ── Message Builders & Keyboards ─────────────────────────────────────────────

_LOW_CONFIDENCE_THRESHOLD: float = float(os.getenv("RECEIPT_LOW_CONFIDENCE", "0.80"))


def _confidence_pct(receipt: dict) -> Optional[float]:
    """Confidence (0-1) as a percentage, or None when absent/invalid."""
    conf = receipt.get("confidence")
    if conf is None:
        return None
    try:
        return float(conf) * 100
    except (TypeError, ValueError):
        return None


def build_confirmation_text(receipt: dict, edit_target: Optional[str] = None, current_index: int = 0, total_count: int = 1) -> str:
    tx_type = (receipt.get("transaction_type") or receipt.get("type") or "expense").lower()
    if tx_type == "transfer":
        return _build_transfer_confirmation_text(
            receipt, edit_target=edit_target, current_index=current_index, total_count=total_count
        )

    merchant = receipt.get("merchant_name") or receipt.get("merchant") or "Tidak diketahui"
    total = receipt.get("total_amount")
    if total is None:
        total = receipt.get("amount") or 0
    category = receipt.get("category") or "Food & Drink"
    if category == "food":
        category = "Food & Drink"

    raw_date = str(receipt.get("transaction_date") or receipt.get("date") or time.strftime("%Y-%m-%d"))
    date_str = raw_date.split("T")[0].split(" ")[0]

    payment = receipt.get("payment_method") or "QRIS"
    if payment == "qris": payment = "QRIS"
    elif payment == "bank-transfer": payment = "Bank Transfer"

    tx_type = receipt.get("transaction_type") or receipt.get("type") or "expense"

    # Format amount
    try:
        total_val = float(total)
        total_formatted = f"Rp {total_val:,.0f}".replace(",", ".")
    except Exception:
        total_formatted = str(total)

    header_title = "📝 <b>Konfirmasi Struk Belanja</b>"
    if total_count > 1:
        header_title += f" <b>({current_index + 1} dari {total_count})</b>"

    text = (
        f"{header_title}\n\n"
        f"• <b>Merchant:</b> {merchant}\n"
        f"• <b>Total:</b> {total_formatted}\n"
        f"• <b>Kategori:</b> {category}\n"
        f"• <b>Tanggal:</b> {date_str}\n"
        f"• <b>Metode Pembayaran:</b> {payment}\n"
        f"• <b>Tipe:</b> {'Pengeluaran' if tx_type == 'expense' else 'Pemasukan'}\n"
    )

    # Phase 4 — OCR confidence visibility; low confidence → warning
    conf_pct = _confidence_pct(receipt)
    if conf_pct is not None:
        text += f"• <b>Kepercayaan OCR:</b> {conf_pct:.0f}%\n"
    text += "\n"
    if conf_pct is not None and conf_pct < _LOW_CONFIDENCE_THRESHOLD * 100:
        text += "⚠️ <b>Akurasi rendah</b> — periksa detail sebelum menyimpan.\n\n"

    if edit_target == "merchant_name":
        text += "👉 <b>Silakan ketik NAMA MERCHANT baru di chat ini...</b>"
    elif edit_target == "total_amount":
        text += "👉 <b>Silakan ketik NOMINAL TOTAL baru (angka saja, misal: 25000) di chat ini...</b>"
    elif edit_target == "transaction_date":
        text += "👉 <b>Pilih tombol preset di bawah atau ketik TANGGAL baru (YYYY-MM-DD) di chat...</b>"
    else:
        text += "<i>Periksa detail di atas. Klik tombol di bawah untuk mengedit atau menyimpan.</i>"

    return text


def _build_transfer_confirmation_text(
    receipt: dict,
    edit_target: Optional[str] = None,
    current_index: int = 0,
    total_count: int = 1,
) -> str:
    """Render a transfer draft (Dari → Ke) for confirmation."""
    from_acc = receipt.get("from_account") or receipt.get("from") or "Tidak diketahui"
    to_acc = receipt.get("to_account") or receipt.get("to") or "Tidak diketahui"
    total = receipt.get("total_amount")
    if total is None:
        total = receipt.get("amount") or 0
    try:
        total_formatted = f"Rp {float(total):,.0f}".replace(",", ".")
    except Exception:
        total_formatted = str(total)

    raw_date = str(receipt.get("transaction_date") or receipt.get("date") or time.strftime("%Y-%m-%d"))
    date_str = raw_date.split("T")[0].split(" ")[0]
    description = str(receipt.get("description") or "").strip()

    header = "🔄 <b>Konfirmasi Transfer</b>"
    if total_count > 1:
        header += f" <b>({current_index + 1} dari {total_count})</b>"

    text = (
        f"{header}\n\n"
        f"• <b>Dari:</b> {from_acc}\n"
        f"• <b>Ke:</b> {to_acc}\n"
        f"• <b>Nominal:</b> {total_formatted}\n"
        f"• <b>Tanggal:</b> {date_str}\n"
    )
    if description:
        text += f"• <b>Deskripsi:</b> {description}\n"
    text += "\n"

    if edit_target == "from_account":
        text += "👉 <b>Silakan ketik NAMA REKENING ASAL baru di chat ini...</b>"
    elif edit_target == "to_account":
        text += "👉 <b>Silakan ketik NAMA REKENING TUJUAN baru di chat ini...</b>"
    elif edit_target == "transaction_date":
        text += "👉 <b>Pilih tombol preset di bawah atau ketik TANGGAL baru (YYYY-MM-DD) di chat...</b>"
    else:
        text += "<i>Periksa detail di atas. Klik tombol di bawah untuk mengedit atau menyimpan.</i>"
    return text


def make_confirmation_keyboard(transaction_type: str = "expense", current_index: int = 0, total_count: int = 1) -> dict:
    tx_key = (transaction_type or "expense").lower()
    if tx_key == "transfer":
        return {
            "inline_keyboard": [
                [
                    {"text": "🏦 Edit Dari", "callback_data": "edit_from_account"},
                    {"text": "🏦 Edit Ke", "callback_data": "edit_to_account"}
                ],
                [
                    {"text": "📅 Edit Tanggal", "callback_data": "edit_date"}
                ],
                [
                    {"text": "✅ Simpan / Konfirmasi", "callback_data": "confirm_save"},
                    {"text": "❌ Batal", "callback_data": "confirm_cancel"}
                ]
            ]
        }

    btn_save_text = "✅ Simpan / Konfirmasi"
    if total_count > 1:
        btn_save_text = f"✅ Simpan & Lanjut ({current_index + 1}/{total_count})"

    rows = [
        [
            {"text": "📝 Edit Merchant", "callback_data": "edit_merchant"},
            {"text": "💰 Edit Total", "callback_data": "edit_amount"}
        ],
        [
            {"text": "📅 Edit Tanggal", "callback_data": "edit_date"},
            {"text": "🏷️ Edit Kategori", "callback_data": "edit_category"}
        ],
        [
            {"text": "💳 Edit Pembayaran", "callback_data": "edit_payment"}
        ],
        [
            {"text": btn_save_text, "callback_data": "confirm_save"}
        ]
    ]

    if total_count > 1:
        rows.append([
            {"text": "⏩ Lewati Struk Ini", "callback_data": "skip_receipt"},
            {"text": "❌ Batal Semua", "callback_data": "confirm_cancel"}
        ])
    else:
        rows[-1].append({"text": "❌ Batal", "callback_data": "confirm_cancel"})

    return {"inline_keyboard": rows}


def make_category_keyboard(transaction_type: str = "expense") -> dict:
    if transaction_type == "expense":
        return {
            "inline_keyboard": [
                [
                    {"text": "Food & Drink 🍔", "callback_data": "set_cat:Food & Drink"},
                    {"text": "Transport 🚗", "callback_data": "set_cat:transport"},
                    {"text": "Housing 🏠", "callback_data": "set_cat:housing"}
                ],
                [
                    {"text": "Ent. 🎬", "callback_data": "set_cat:entertainment"},
                    {"text": "Health 🏥", "callback_data": "set_cat:health"},
                    {"text": "Shopping 🛍️", "callback_data": "set_cat:shopping"}
                ],
                [
                    {"text": "Edu 📚", "callback_data": "set_cat:education"},
                    {"text": "Invest 📈", "callback_data": "set_cat:investment"},
                    {"text": "Other 🧩", "callback_data": "set_cat:other"}
                ],
                [
                    {"text": "⬅️ Kembali", "callback_data": "back_to_confirm"}
                ]
            ]
        }
    else:
        return {
            "inline_keyboard": [
                [
                    {"text": "Salary 💵", "callback_data": "set_cat:salary"},
                    {"text": "Freelance 💻", "callback_data": "set_cat:freelance"},
                    {"text": "Investment 📈", "callback_data": "set_cat:investment"}
                ],
                [
                    {"text": "Side Hustle 🚀", "callback_data": "set_cat:side-hustle"},
                    {"text": "Transfer 🔄", "callback_data": "set_cat:transfer"},
                    {"text": "Other 🧩", "callback_data": "set_cat:other"}
                ],
                [
                    {"text": "⬅️ Kembali", "callback_data": "back_to_confirm"}
                ]
            ]
        }


def make_payment_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "QRIS 📱", "callback_data": "set_pay:QRIS"},
                {"text": "Bank Transfer 🏦", "callback_data": "set_pay:Bank Transfer"}
            ],
            [
                {"text": "Debit Card 💳", "callback_data": "set_pay:debit-card"},
                {"text": "E-Wallet 👛", "callback_data": "set_pay:e-wallet"}
            ],
            [
                {"text": "Cash 💵", "callback_data": "set_pay:cash"}
            ],
            [
                {"text": "⬅️ Kembali", "callback_data": "back_to_confirm"}
            ]
        ]
    }


def make_date_keyboard() -> dict:
    from datetime import datetime, timedelta
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return {
        "inline_keyboard": [
            [
                {"text": f"📅 Hari Ini ({today_str})", "callback_data": f"set_date:{today_str}"},
                {"text": f"⏮️ Kemarin ({yesterday_str})", "callback_data": f"set_date:{yesterday_str}"}
            ],
            [
                {"text": "✏️ Ketik Tanggal Manual", "callback_data": "edit_date_manual"}
            ],
            [
                {"text": "⬅️ Kembali", "callback_data": "back_to_confirm"}
            ]
        ]
    }

# ── Event Handlers ───────────────────────────────────────────────────────────

async def handle_callback_query(callback_query_id: str, chat_id: int, message_id: int, data: str):
    """Processes inline keyboard button clicks."""
    session = PENDING_RECEIPTS.get(chat_id)
    await answer_callback_query(callback_query_id)

    if not session:
        await send_message(chat_id, "⚠️ Sesi konfirmasi telah kedaluwarsa atau tidak ditemukan.")
        return

    active = _active_draft(chat_id)
    if not active:
        PENDING_RECEIPTS.pop(chat_id, None)
        await send_message(chat_id, "⚠️ Draft konfirmasi tidak ditemukan di penyimpanan.")
        return

    token = active["token"]
    receipt = dict(active["row"]["draft"])
    idx = session.get("current_index", 0)
    tokens = session.get("tokens") or []
    total_count = len(tokens)

    if data == "confirm_cancel":
        try:
            _ce().cancel_draft(_chat_db(), token)
            _ce().cancel_all_pending(_chat_db(), chat_id)
        except Exception as e:
            logger.warning(f"Cancel failed for chat {chat_id}: {e}")
        PENDING_RECEIPTS.pop(chat_id, None)
        await edit_message(
            chat_id,
            message_id,
            "❌ <b>Pencatatan struk dibatalkan.</b>",
            reply_markup={"inline_keyboard": []}
        )

    elif data in ("confirm_save", "skip_receipt"):
        should_save = (data == "confirm_save")
        saved_count = session.get("saved_count", 0)

        if should_save:
            try:
                result = _ce().confirm_draft(_chat_db(), token, ledger_db_path=_ledger_db())
                saved_count += 1
                session["saved_count"] = saved_count
                logger.info(f"Confirmed ledger tx {result['transaction']['id']} for chat {chat_id}")
            except Exception as e:
                logger.warning(f"Confirm failed for chat {chat_id}: {e}")
                await send_message(chat_id, f"⚠️ Gagal menyimpan transaksi: {e}")
        else:
            try:
                _ce().cancel_draft(_chat_db(), token)
            except Exception as e:
                logger.warning(f"Skip-cancel failed for chat {chat_id}: {e}")

        # Advance to next item in queue
        next_idx = idx + 1
        if next_idx < total_count:
            session["current_index"] = next_idx
            nxt = _active_draft(chat_id)
            next_receipt = dict(nxt["row"]["draft"]) if nxt else {}

            text = build_confirmation_text(next_receipt, current_index=next_idx, total_count=total_count)
            keyboard = make_confirmation_keyboard(next_receipt.get("transaction_type", next_receipt.get("type", "expense")), current_index=next_idx, total_count=total_count)
            await edit_message(chat_id, message_id, text, reply_markup=keyboard)
        else:
            PENDING_RECEIPTS.pop(chat_id, None)
            summary_text = (
                "✅ <b>Proses Pemindaian Struk Selesai!</b>\n\n"
                f"• <b>Total Struk Disimpan:</b> {saved_count} dari {total_count}\n"
                f"• <b>Status:</b> Berhasil masuk ke database."
            )
            await edit_message(chat_id, message_id, summary_text, reply_markup={"inline_keyboard": []})

    elif data == "edit_from_account":
        _ce().update_draft(_chat_db(), token, edit_target="from_account")
        text = build_confirmation_text(receipt, edit_target="from_account", current_index=idx, total_count=total_count)
        keyboard = {"inline_keyboard": [[{"text": "⬅️ Batal Edit", "callback_data": "back_to_confirm"}]]}
        await edit_message(chat_id, message_id, text, reply_markup=keyboard)

    elif data == "edit_to_account":
        _ce().update_draft(_chat_db(), token, edit_target="to_account")
        text = build_confirmation_text(receipt, edit_target="to_account", current_index=idx, total_count=total_count)
        keyboard = {"inline_keyboard": [[{"text": "⬅️ Batal Edit", "callback_data": "back_to_confirm"}]]}
        await edit_message(chat_id, message_id, text, reply_markup=keyboard)

    elif data == "edit_merchant":
        _ce().update_draft(_chat_db(), token, edit_target="merchant_name")
        text = build_confirmation_text(receipt, edit_target="merchant_name", current_index=idx, total_count=total_count)
        keyboard = {"inline_keyboard": [[{"text": "⬅️ Batal Edit", "callback_data": "back_to_confirm"}]]}
        await edit_message(chat_id, message_id, text, reply_markup=keyboard)

    elif data == "edit_amount":
        _ce().update_draft(_chat_db(), token, edit_target="total_amount")
        text = build_confirmation_text(receipt, edit_target="total_amount", current_index=idx, total_count=total_count)
        keyboard = {"inline_keyboard": [[{"text": "⬅️ Batal Edit", "callback_data": "back_to_confirm"}]]}
        await edit_message(chat_id, message_id, text, reply_markup=keyboard)

    elif data == "edit_date":
        keyboard = make_date_keyboard()
        await edit_message(chat_id, message_id, build_confirmation_text(receipt, current_index=idx, total_count=total_count), reply_markup=keyboard)

    elif data == "edit_date_manual":
        _ce().update_draft(_chat_db(), token, edit_target="transaction_date")
        text = build_confirmation_text(receipt, edit_target="transaction_date", current_index=idx, total_count=total_count)
        keyboard = {"inline_keyboard": [[{"text": "⬅️ Batal Edit", "callback_data": "back_to_confirm"}]]}
        await edit_message(chat_id, message_id, text, reply_markup=keyboard)

    elif data == "edit_category":
        keyboard = make_category_keyboard(receipt.get("transaction_type", receipt.get("type", "expense")))
        await edit_message(chat_id, message_id, build_confirmation_text(receipt, current_index=idx, total_count=total_count), reply_markup=keyboard)

    elif data == "edit_payment":
        keyboard = make_payment_keyboard()
        await edit_message(chat_id, message_id, build_confirmation_text(receipt, current_index=idx, total_count=total_count), reply_markup=keyboard)

    elif data.startswith("set_cat:"):
        cat_name = data.split(":", 1)[1]
        receipt["category"] = cat_name
        _ce().update_draft(_chat_db(), token, draft=receipt)
        text = build_confirmation_text(receipt, current_index=idx, total_count=total_count)
        keyboard = make_confirmation_keyboard(receipt.get("transaction_type", receipt.get("type", "expense")), current_index=idx, total_count=total_count)
        await edit_message(chat_id, message_id, text, reply_markup=keyboard)

    elif data.startswith("set_pay:"):
        pay_name = data.split(":", 1)[1]
        receipt["payment_method"] = pay_name
        _ce().update_draft(_chat_db(), token, draft=receipt)
        text = build_confirmation_text(receipt, current_index=idx, total_count=total_count)
        keyboard = make_confirmation_keyboard(receipt.get("transaction_type", receipt.get("type", "expense")), current_index=idx, total_count=total_count)
        await edit_message(chat_id, message_id, text, reply_markup=keyboard)

    elif data.startswith("set_date:"):
        d_val = data.split(":", 1)[1]
        receipt["transaction_date"] = d_val
        _ce().update_draft(_chat_db(), token, draft=receipt)
        text = build_confirmation_text(receipt, current_index=idx, total_count=total_count)
        keyboard = make_confirmation_keyboard(receipt.get("transaction_type", receipt.get("type", "expense")), current_index=idx, total_count=total_count)
        await edit_message(chat_id, message_id, text, reply_markup=keyboard)

    elif data == "back_to_confirm":
        _ce().update_draft(_chat_db(), token, edit_target="")
        text = build_confirmation_text(receipt, current_index=idx, total_count=total_count)
        keyboard = make_confirmation_keyboard(receipt.get("transaction_type", receipt.get("type", "expense")), current_index=idx, total_count=total_count)
        await edit_message(chat_id, message_id, text, reply_markup=keyboard)


from fastapi import Depends

from packages.api.backend.security.core import require_scope

# ── FastAPI Router ───────────────────────────────────────────────────────────

router = APIRouter(prefix="/telegram", tags=["telegram"], dependencies=[Depends(require_scope("write"))])

class ReceiptPendingBody(BaseModel):
    chat_id: int
    receipts: List[Dict[str, Any]]

@router.post("/receipt_pending")
async def telegram_receipt_pending(body: ReceiptPendingBody) -> JSONResponse:
    """
    Receives scanned receipt data from n8n and starts the confirmation flow.
    Supports single or bulk receipt items.
    """
    chat_id = body.chat_id
    if not body.receipts:
        await send_message(chat_id, "❌ Tidak ada data struk yang terbaca dari foto tersebut. Silakan coba lagi dengan foto yang lebih jelas.")
        return JSONResponse({"status": "error", "message": "No receipts provided"})

    # Auto-sanitize each receipt item, then reject invalid ones up-front
    # (Phase 4 hardening: no silent ledger failures downstream).
    for receipt in body.receipts:
        if receipt.get("category") == "food":
            receipt["category"] = "Food & Drink"

        raw_date = str(receipt.get("transaction_date") or time.strftime("%Y-%m-%d"))
        receipt["transaction_date"] = raw_date.split("T")[0].split(" ")[0]

        pay_method = receipt.get("payment_method")
        if pay_method == "qris": receipt["payment_method"] = "QRIS"
        elif pay_method == "bank-transfer": receipt["payment_method"] = "Bank Transfer"

    valid_receipts: List[Dict[str, Any]] = []
    rejected: List[str] = []
    for receipt in body.receipts:
        errors = _ce().validate_draft_fields(receipt)
        if errors:
            name = str(receipt.get("merchant_name") or receipt.get("merchant") or "?")
            rejected.append(f"{name} → {'; '.join(errors)}")
        else:
            valid_receipts.append(receipt)

    if rejected:
        await send_message(
            chat_id,
            "⚠️ <b>Beberapa struk tidak valid dan diabaikan:</b>\n"
            + "\n".join(f"• {r}" for r in rejected[:5])
            + ("\n…" if len(rejected) > 5 else ""),
        )

    if not valid_receipts:
        await send_message(
            chat_id,
            "❌ <b>Data struk tidak valid.</b> Tidak ada yang bisa diproses.\n\n"
            "Silakan kirim foto struk yang lebih jelas.",
        )
        return JSONResponse({"status": "error", "message": "No valid receipts provided"})

    receipts_to_process = valid_receipts

    existing = PENDING_RECEIPTS.get(chat_id)
    if existing and existing.get("tokens"):
        # Append additional bulk receipts to the persistent store queue
        new_tokens = []
        for receipt in receipts_to_process:
            draft = _ce().create_draft(_chat_db(), chat_id, receipt)
            new_tokens.append(draft["token"])
        existing["tokens"].extend(new_tokens)
        total_count = len(existing["tokens"])
        idx = existing.get("current_index", 0)
        curr_receipt = _draft_receipt(chat_id) or {}
        active = _active_draft(chat_id)

        text = build_confirmation_text(curr_receipt, current_index=idx, total_count=total_count)
        keyboard = make_confirmation_keyboard(curr_receipt.get("transaction_type", curr_receipt.get("type", "expense")), current_index=idx, total_count=total_count)
        if active and active["row"].get("message_id"):
            await edit_message(chat_id, active["row"]["message_id"], text, reply_markup=keyboard)
        return JSONResponse({"status": "ok", "message": f"Appended {len(receipts_to_process)} receipts to queue"})

    # Persist each receipt as a draft in the confirmation store (Phase 3)
    _ensure_chat_bound(chat_id)
    tokens = []
    for receipt in receipts_to_process:
        draft = _ce().create_draft(_chat_db(), chat_id, receipt)
        tokens.append(draft["token"])

    PENDING_RECEIPTS[chat_id] = {
        "tokens": tokens,
        "current_index": 0,
    }

    first_receipt = body.receipts[0]
    total_count = len(body.receipts)
    text = build_confirmation_text(first_receipt, current_index=0, total_count=total_count)
    keyboard = make_confirmation_keyboard(first_receipt.get("transaction_type", first_receipt.get("type", "expense")), current_index=0, total_count=total_count)

    resp = await send_message(chat_id, text, reply_markup=keyboard)
    msg_id = resp.get("result", {}).get("message_id")
    if msg_id:
        try:
            _ce().update_draft(_chat_db(), tokens[0], message_id=msg_id)
        except Exception as e:
            logger.warning(f"Failed to store message_id on draft: {e}")

    return JSONResponse({"status": "ok", "message_id": msg_id})


@router.post("/webhook")
async def telegram_webhook(request: Request) -> JSONResponse:
    """
    Webhook endpoint — n8n posts raw Telegram updates here.
    """
    if not TELEGRAM_WEBHOOK_SECRET:
        logger.error("Telegram webhook is disabled: TELEGRAM_WEBHOOK_SECRET is not configured")
        raise HTTPException(status_code=503, detail="Webhook is not configured")
    supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(supplied_secret, TELEGRAM_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Handle Callback Queries (button clicks)
    if "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb.get("id")
        chat_id = cb.get("message", {}).get("chat", {}).get("id")
        msg_id = cb.get("message", {}).get("message_id")
        data = cb.get("data", "")

        if cb_id and chat_id and msg_id:
            await handle_callback_query(cb_id, chat_id, msg_id, data)
        return JSONResponse({"status": "ok"})

    # Handle Messages (text entries)
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    user_name = message.get("from", {}).get("first_name", "User")

    if not chat_id:
        raise HTTPException(status_code=400, detail="Missing chat.id in payload")

    # Guard against photo/document updates since file processing flows through n8n OCR nodes
    if message.get("photo") or message.get("document"):
        return JSONResponse({"status": "ignored", "reason": "photo/document message — handled by n8n OCR flow"})

    session = PENDING_RECEIPTS.get(chat_id)
    active = _active_draft(chat_id)

    # User is in active editing mode
    if active and active["row"].get("edit_target"):
        target = active["row"]["edit_target"]
        val = text.strip()
        receipt = dict(active["row"]["draft"])
        idx = session.get("current_index", 0)
        total_count = len(session.get("tokens") or [active["token"]])

        if target == "total_amount":
            try:
                val_clean = val.lower().replace("rp", "").replace(".", "").replace(",", "").strip()
                if "k" in val_clean:
                    val_clean = val_clean.replace("k", "")
                    val_num = float(val_clean) * 1000
                elif "rb" in val_clean:
                    val_clean = val_clean.replace("rb", "")
                    val_num = float(val_clean) * 1000
                elif "jt" in val_clean:
                    val_clean = val_clean.replace("jt", "")
                    val_num = float(val_clean) * 1000000
                else:
                    val_num = float(val_clean)
                receipt["total_amount"] = val_num
                receipt["amount"] = val_num
            except ValueError:
                await send_message(chat_id, "⚠️ Nominal tidak valid. Silakan kirim angka saja (contoh: 50000).")
                return JSONResponse({"status": "error", "reason": "invalid amount"})
        elif target == "from_account":
            receipt["from_account"] = val
        elif target == "to_account":
            receipt["to_account"] = val
        elif target == "transaction_date":
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", val):
                await send_message(chat_id, "⚠️ Format tanggal salah. Gunakan format YYYY-MM-DD (contoh: 2026-07-20).")
                return JSONResponse({"status": "error", "reason": "invalid date format"})
            receipt["transaction_date"] = val
            receipt["date"] = val
        else:
            receipt["merchant_name"] = val

        _ce().update_draft(_chat_db(), active["token"], draft=receipt, edit_target="")
        new_text = build_confirmation_text(receipt, current_index=idx, total_count=total_count)
        new_keyboard = make_confirmation_keyboard(receipt.get("transaction_type", receipt.get("type", "expense")), current_index=idx, total_count=total_count)
        msg_id = active["row"].get("message_id")
        if msg_id:
            await edit_message(chat_id, msg_id, new_text, reply_markup=new_keyboard)
        else:
            await send_message(chat_id, new_text, reply_markup=new_keyboard)
        return JSONResponse({"status": "ok", "action": "edited"})

    # User sent text, but there's an unconfirmed draft they are NOT currently editing
    if active:
        warn_text = (
            "⚠️ <b>Ada transaksi yang belum selesai dikonfirmasi!</b>\n\n"
            "Silakan gunakan tombol pada pesan di atas untuk mengkonfirmasi atau membatalkan pencatatan struk tersebut.\n\n"
            "Jika ingin membatalkan, klik tombol <b>Batal</b> pada pesan struk."
        )
        await send_message(chat_id, warn_text)
        return JSONResponse({"status": "ok", "action": "warning_sent"})

    # Explicit commands & manual adds -> existing handler (direct save)
    if _is_explicit_command(text):
        try:
            from packages.api.telegram_handler import handle_telegram_text
            reply = await handle_telegram_text(chat_id, text, user_name)
            await send_message(chat_id, reply)
            return JSONResponse({"status": "ok", "action": "processed"})
        except Exception as e:
            logger.exception("Failed to process text message in webhook")
            await send_message(chat_id, f"❌ Error processing message: {e}")
            return JSONResponse({"status": "error", "reason": str(e)})

    # Free-form NL finance questions (Phase 11): intent -> backend computes -> explanation
    intent_reply = _handle_finance_intent(text)
    if intent_reply is not None:
        await send_message(chat_id, intent_reply)
        return JSONResponse({"status": "ok", "action": "processed"})

    # Free-form NL text -> parse -> persistent draft -> confirmation (Phase 3)
    try:
        draft = _parse_nl_text(text)
        if not draft or not draft.get("amount"):
            await send_message(
                chat_id,
                "❓ Pesan tidak dikenali.\n\nKetik <b>help</b> untuk melihat format perintah, "
                "atau kirim foto struk untuk scan OCR."
            )
            return JSONResponse({"status": "ok", "action": "unknown"})

        _ensure_chat_bound(chat_id)
        out = _ce().create_draft(_chat_db(), chat_id, draft)
        PENDING_RECEIPTS[chat_id] = {"tokens": [out["token"]], "current_index": 0}

        text_out = build_confirmation_text(draft, current_index=0, total_count=1)
        keyboard = make_confirmation_keyboard(draft.get("transaction_type", draft.get("type", "expense")), current_index=0, total_count=1)
        resp = await send_message(chat_id, text_out, reply_markup=keyboard)
        msg_id = resp.get("result", {}).get("message_id")
        if msg_id:
            try:
                _ce().update_draft(_chat_db(), out["token"], message_id=msg_id)
            except Exception as e:
                logger.warning(f"Failed to store message_id on NL draft: {e}")
        return JSONResponse({"status": "ok", "action": "draft_created"})
    except Exception as e:
        logger.exception("NL parse/draft flow failed")
        await send_message(chat_id, f"❌ Error processing message: {e}")
        return JSONResponse({"status": "error", "reason": str(e)})


@router.get("/health")
async def telegram_health() -> dict:
    """Quick check that the bot token is configured."""
    return {
        "status": "ok" if TELEGRAM_BOT_TOKEN else "unconfigured",
        "token_set": bool(TELEGRAM_BOT_TOKEN),
    }

# ── Standalone entrypoint ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI

    standalone_app = FastAPI(title="Finance Tracker Telegram Bot")
    standalone_app.include_router(router)

    port = int(os.getenv("TELEGRAM_BOT_PORT", "8445"))
    print(f"[*] Telegram Bot webhook listening on :{port}/telegram/webhook")
    uvicorn.run(standalone_app, host="0.0.0.0", port=port, log_level="info")
