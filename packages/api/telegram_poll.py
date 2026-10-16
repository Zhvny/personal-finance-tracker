#!/usr/bin/env python3
"""
Finance Tracker — Telegram Bot Polling Runner
==============================================
Standalone mode: polls Telegram getUpdates every 2s.
Does NOT require n8n — use this when you just want the bot
to respond locally without setting up n8n.

Usage:
    python packages/api/telegram_poll.py
"""

import asyncio
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv

# ── Setup ────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
load_dotenv(_HERE / ".env")

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
_PORT = os.getenv("FINANCE_TRACKER_PORT", "8444")
API_SERVER_URL = os.getenv("API_SERVER_URL", f"http://localhost:{_PORT}")

async def call_api_post(client: httpx.AsyncClient, path: str, **kwargs) -> httpx.Response:
    """Robustly post to API server trying multiple localhost/127.0.0.1/IP combinations."""
    urls_to_try = [
        f"{API_SERVER_URL}{path}",
        f"http://127.0.0.1:{_PORT}{path}",
        f"https://127.0.0.1:{_PORT}{path}",
        f"http://localhost:{_PORT}{path}",
        f"https://localhost:{_PORT}{path}",
    ]
    seen = set()
    unique_urls = [u for u in urls_to_try if not (u in seen or seen.add(u))]

    last_exc = None
    for url in unique_urls:
        try:
            resp = await client.post(url, **kwargs)
            return resp
        except Exception as exc:
            last_exc = exc
            logger.debug("Failed calling API endpoint %s: %s", url, exc)
    if last_exc:
        raise last_exc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("telegram_poll")

# In-memory session store for pending confirmations
# Schema: { chat_id: { "receipt": dict, "status": str, "edit_target": str, "message_id": int } }
PENDING_RECEIPTS: Dict[int, Dict[str, Any]] = {}

# ── Telegram helpers ──────────────────────────────────────────────────────────

async def tg(client: httpx.AsyncClient, method: str, **kwargs) -> dict:
    resp = await client.post(f"{BASE_URL}/{method}", json=kwargs, timeout=15)
    resp.raise_for_status()
    return resp.json().get("result", {})


async def send_msg(client: httpx.AsyncClient, chat_id: int | str, text: str, parse_mode: str = "HTML", reply_markup: Optional[dict] = None) -> dict:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await tg(client, "sendMessage", **payload)


async def edit_msg(client: httpx.AsyncClient, chat_id: int | str, message_id: int, text: str, parse_mode: str = "HTML", reply_markup: Optional[dict] = None) -> Optional[dict]:
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        return await tg(client, "editMessageText", **payload)
    except Exception as e:
        logger.warning("edit_msg failed (chat=%s msg=%s): %s", chat_id, message_id, e)
        return None


async def answer_callback(client: httpx.AsyncClient, callback_query_id: str, text: Optional[str] = None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    try:
        await tg(client, "answerCallbackQuery", **payload)
    except Exception:
        pass


async def typing(client: httpx.AsyncClient, chat_id: int | str):
    try:
        await tg(client, "sendChatAction", chat_id=chat_id, action="typing")
    except Exception:
        pass

# ── Message builders & Keyboards ─────────────────────────────────────────────

_LOW_CONFIDENCE_THRESHOLD: float = float(os.getenv("RECEIPT_LOW_CONFIDENCE", "0.80"))


def build_confirmation_text(receipt: dict, edit_target: Optional[str] = None) -> str:
    merchant = receipt.get("merchant_name") or "Tidak diketahui"
    total = receipt.get("total_amount") or 0
    category = receipt.get("category") or "other"
    date_str = receipt.get("transaction_date") or time.strftime("%Y-%m-%d")
    tx_type = receipt.get("transaction_type") or "expense"

    try:
        total_val = float(total)
        total_formatted = f"Rp {total_val:,.0f}".replace(",", ".")
    except Exception:
        total_formatted = str(total)

    conf_pct = None
    try:
        if receipt.get("confidence") is not None:
            conf_pct = float(receipt["confidence"]) * 100
    except (TypeError, ValueError):
        conf_pct = None

    text = (
        "📝 <b>Konfirmasi Struk Belanja</b>\n\n"
        f"• <b>Merchant:</b> {merchant}\n"
        f"• <b>Total:</b> {total_formatted}\n"
        f"• <b>Kategori:</b> {category}\n"
        f"• <b>Tanggal:</b> {date_str}\n"
        f"• <b>Tipe:</b> {'Pengeluaran' if tx_type == 'expense' else 'Pemasukan'}\n"
    )
    if conf_pct is not None:
        text += f"• <b>Kepercayaan OCR:</b> {conf_pct:.0f}%\n"
    text += "\n"
    if conf_pct is not None and conf_pct < _LOW_CONFIDENCE_THRESHOLD * 100:
        text += "⚠️ <b>Akurasi rendah</b> — periksa detail sebelum menyimpan.\n\n"

    if edit_target == "merchant_name":
        text += "👉 <b>Silakan ketik NAMA MERCHANT baru di chat ini...</b>"
    elif edit_target == "total_amount":
        text += "👉 <b>Silakan ketik NOMINAL TOTAL baru (angka saja) di chat ini...</b>"
    elif edit_target == "transaction_date":
        text += "👉 <b>Silakan ketik TANGGAL baru (YYYY-MM-DD) di chat ini...</b>"
    else:
        text += "<i>Periksa detail di atas. Klik tombol di bawah untuk mengedit atau menyimpan.</i>"

    return text


def make_confirmation_keyboard(transaction_type: str = "expense") -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "📝 Edit Merchant", "callback_data": "edit_merchant"},
                {"text": "💰 Edit Total", "callback_data": "edit_amount"}
            ],
            [
                {"text": "📅 Edit Tanggal", "callback_data": "edit_date"},
                {"text": "🏷️ Edit Kategori", "callback_data": "edit_category"}
            ],
            [
                {"text": "✅ Simpan / Konfirmasi", "callback_data": "confirm_save"},
                {"text": "❌ Batal", "callback_data": "confirm_cancel"}
            ]
        ]
    }


def make_category_keyboard(transaction_type: str = "expense") -> dict:
    if transaction_type == "expense":
        return {
            "inline_keyboard": [
                [
                    {"text": "Food 🍔", "callback_data": "set_cat:food"},
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

HELP_TEXT = (
    "🤖 <b>Finance Tracker Bot</b>\n\n"
    "Bot ini digunakan untuk mencatat pengeluaran/pemasukan Anda secara otomatis menggunakan foto struk.\n\n"
    "<b>Cara Penggunaan:</b>\n"
    "1. 📷 <b>Kirim Foto Struk/Kuitansi</b> ke chat ini.\n"
    "2. ⏳ Bot akan mengunduh dan menganalisis struk menggunakan OCR.\n"
    "3. 📌 Konfirmasi hasil scan OCR di layar, lalu klik <b>Simpan</b>.\n\n"
    "<i>Pesan teks biasa tidak dicatat ke database. Kirim foto untuk mulai mencatat.</i>"
)

# ── Message templates ─────────────────────────────────────────────────────────

def build_progress(step, total, label):
    filled = round((step / total) * 10)
    bar = "▓" * filled + "░" * (10 - filled)
    pct = round((step / total) * 100)
    return f"⏳ <b>{label}</b>\n<code>{bar}</code> {pct}%\n<i>Langkah {step}/{total}</i>"

# ── Callback Query handler ────────────────────────────────────────────────────

async def handle_callback(client: httpx.AsyncClient, cb: dict):
    cb_id = cb.get("id")
    chat_id = cb.get("message", {}).get("chat", {}).get("id")
    msg_id = cb.get("message", {}).get("message_id")
    data = cb.get("data", "")

    if not chat_id or not msg_id or not cb_id:
        return

    await answer_callback(client, cb_id)
    session = PENDING_RECEIPTS.get(chat_id)

    if not session:
        await send_msg(client, chat_id, "⚠️ Sesi konfirmasi telah kedaluwarsa atau tidak ditemukan.")
        return

    if data == "confirm_cancel":
        PENDING_RECEIPTS.pop(chat_id, None)
        await edit_msg(
            client, chat_id, msg_id,
            "❌ <b>Pencatatan struk dibatalkan.</b>",
            reply_markup={"inline_keyboard": []}
        )

    elif data == "confirm_save":
        receipt = session["receipt"]
        target = receipt.get("transaction_type") or "expense"
        amount = receipt.get("total_amount") or 0
        merchant = receipt.get("merchant_name") or "Unknown"
        category = receipt.get("category") or "other"
        payment = receipt.get("payment_method") or "cash"
        date_raw = receipt.get("transaction_date") or time.strftime("%Y-%m-%d")

        success = False
        error_msg = ""

        try:
            # Phase 3 — unify the write path on the ledger via the confirmation API:
            # draft -> confirm (one-time token, 24h TTL, idempotent ledger commit).
            bind_resp = await call_api_post(
                client,
                "/api/chat-bindings",
                json={"chat_id": chat_id},
                timeout=15,
            )
            draft_resp = await call_api_post(
                client,
                "/api/confirmations/drafts",
                json={
                    "chat_id": chat_id,
                    "draft": {
                        "merchant_name": merchant,
                        "transaction_date": date_raw,
                        "total_amount": amount,
                        "amount": amount,
                        "category": category,
                        "payment_method": payment,
                        "type": target,
                    },
                },
                timeout=15,
            )
            if draft_resp.status_code == 200 and draft_resp.json().get("token"):
                token = draft_resp.json()["token"]
                confirm_resp = await call_api_post(
                    client,
                    f"/api/confirmations/{token}/confirm",
                    json={},
                    timeout=15,
                )
                if confirm_resp.status_code == 200 and confirm_resp.json().get("transaction"):
                    success = True
                else:
                    error_msg = f"Confirm API Error: {confirm_resp.text}"
            else:
                error_msg = f"Draft API Error: {draft_resp.text}"
        except Exception as e:
            logger.exception("Failed to confirm receipt via API")
            error_msg = str(e)

        if success:
            PENDING_RECEIPTS.pop(chat_id, None)
            try:
                amt_formatted = f"Rp {float(amount):,.0f}".replace(",", ".")
            except Exception:
                amt_formatted = str(amount)

            summary_text = (
                "✅ <b>Transaksi Berhasil Disimpan!</b>\n\n"
                f"• <b>Tipe:</b> {'Pengeluaran' if target == 'expense' else 'Pemasukan'}\n"
                f"• <b>Merchant:</b> {merchant}\n"
                f"• <b>Total:</b> {amt_formatted}\n"
                f"• <b>Kategori:</b> {category}\n"
                f"• <b>Tanggal:</b> {date_raw}"
            )
            await edit_msg(client, chat_id, msg_id, summary_text, reply_markup={"inline_keyboard": []})
        else:
            await send_msg(client, chat_id, f"❌ Gagal menyimpan transaksi: {error_msg}")

    elif data == "edit_merchant":
        session["edit_target"] = "merchant_name"
        text = build_confirmation_text(session["receipt"], edit_target="merchant_name")
        keyboard = {"inline_keyboard": [[{"text": "⬅️ Batal Edit", "callback_data": "back_to_confirm"}]]}
        await edit_msg(client, chat_id, msg_id, text, reply_markup=keyboard)

    elif data == "edit_amount":
        session["edit_target"] = "total_amount"
        text = build_confirmation_text(session["receipt"], edit_target="total_amount")
        keyboard = {"inline_keyboard": [[{"text": "⬅️ Batal Edit", "callback_data": "back_to_confirm"}]]}
        await edit_msg(client, chat_id, msg_id, text, reply_markup=keyboard)

    elif data == "edit_date":
        session["edit_target"] = "transaction_date"
        text = build_confirmation_text(session["receipt"], edit_target="transaction_date")
        keyboard = {"inline_keyboard": [[{"text": "⬅️ Batal Edit", "callback_data": "back_to_confirm"}]]}
        await edit_msg(client, chat_id, msg_id, text, reply_markup=keyboard)

    elif data == "edit_category":
        keyboard = make_category_keyboard(session["receipt"].get("transaction_type", "expense"))
        await edit_msg(client, chat_id, msg_id, build_confirmation_text(session["receipt"]), reply_markup=keyboard)

    elif data.startswith("set_cat:"):
        cat_name = data.split(":", 1)[1]
        session["receipt"]["category"] = cat_name
        text = build_confirmation_text(session["receipt"])
        keyboard = make_confirmation_keyboard(session["receipt"].get("transaction_type", "expense"))
        await edit_msg(client, chat_id, msg_id, text, reply_markup=keyboard)

    elif data == "back_to_confirm":
        session["edit_target"] = None
        text = build_confirmation_text(session["receipt"])
        keyboard = make_confirmation_keyboard(session["receipt"].get("transaction_type", "expense"))
        await edit_msg(client, chat_id, msg_id, text, reply_markup=keyboard)

# ── Message handler ───────────────────────────────────────────────────────────

async def handle_message(client: httpx.AsyncClient, message: dict):
    chat_id   = message.get("chat", {}).get("id")
    text      = (message.get("text") or "").strip()
    photo     = message.get("photo")
    user_name = message.get("from", {}).get("first_name", "User")

    if not chat_id:
        return

    logger.info("MSG from %s (%s): %s", user_name, chat_id,
                text[:60] if text else "[photo]")

    # ── Commands ──────────────────────────────────────────────────────────────
    if text in ("/start", "/help"):
        await send_msg(client, chat_id, HELP_TEXT)
        return

    # ── Photo ─────────────────────────────────────────────────────────────────
    if photo:
        await typing(client, chat_id)
        file_id = photo[-1]["file_id"]

        prog = await send_msg(client, chat_id, build_progress(1, 3, "Mengunduh gambar..."))
        prog_id = prog.get("message_id")

        try:
            finfo     = await tg(client, "getFile", file_id=file_id)
            file_path = finfo.get("file_path")
            file_url  = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"

            await edit_msg(client, chat_id, prog_id,
                           build_progress(2, 3, "Menjalankan OCR..."))

            try:
                img_bytes = (await client.get(file_url, timeout=30)).content
            except Exception as dl_err:
                logger.error("Failed to download photo from Telegram: %s", dl_err)
                await edit_msg(client, chat_id, prog_id, f"❌ Gagal mengunduh foto dari Telegram: {str(dl_err)[:100]}")
                return

            await edit_msg(client, chat_id, prog_id,
                           build_progress(3, 3, "Menganalisis struk..."))

            ocr_resp = await call_api_post(
                client,
                "/api/receipt/scan",
                files={"file": ("receipt.jpg", img_bytes, "image/jpeg")},
                timeout=60
            )

            if ocr_resp.status_code == 200:
                data = ocr_resp.json()
                if not data.get("ok") or not data.get("receipts"):
                    await edit_msg(client, chat_id, prog_id, "❌ Gagal membaca struk. Pastikan tulisan struk terlihat jelas.")
                    return

                receipt = data["receipts"][0]

                # Phase 4 — harden: reject invalid OCR results up-front
                from packages.api.backend.finance import confirmation_engine as ce
                draft_errors = ce.validate_draft_fields(receipt)
                if draft_errors:
                    await edit_msg(
                        client, chat_id, prog_id,
                        "❌ <b>Data struk tidak valid:</b>\n• " + "\n• ".join(draft_errors)
                        + "\n\nSilakan kirim foto struk yang lebih jelas."
                    )
                    return

                # Save session
                PENDING_RECEIPTS[chat_id] = {
                    "receipt": receipt,
                    "status": "pending_confirmation",
                    "edit_target": None,
                    "message_id": prog_id
                }

                text_confirm = build_confirmation_text(receipt)
                keyboard = make_confirmation_keyboard(receipt.get("transaction_type", "expense"))

                await edit_msg(client, chat_id, prog_id, text_confirm, reply_markup=keyboard)
            else:
                await edit_msg(client, chat_id, prog_id, f"❌ OCR gagal (HTTP {ocr_resp.status_code})")

        except Exception as exc:
            logger.error("Photo handling error: %s", exc)
            await edit_msg(client, chat_id, prog_id, f"❌ Gagal memproses foto: {str(exc)[:120]}")
        return

    # ── Text message ──────────────────────────────────────────────────────────
    session = PENDING_RECEIPTS.get(chat_id)
    if session and session.get("edit_target"):
        target = session["edit_target"]
        val = text.strip()

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
                session["receipt"]["total_amount"] = val_num
            except ValueError:
                await send_msg(client, chat_id, "⚠️ Nominal tidak valid. Silakan kirim angka saja (contoh: 50000).")
                return
        elif target == "transaction_date":
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", val):
                await send_msg(client, chat_id, "⚠️ Format tanggal salah. Gunakan format YYYY-MM-DD (contoh: 2026-07-20).")
                return
            session["receipt"]["transaction_date"] = val
        else:
            session["receipt"]["merchant_name"] = val

        session["edit_target"] = None
        new_text = build_confirmation_text(session["receipt"])
        new_keyboard = make_confirmation_keyboard(session["receipt"].get("transaction_type", "expense"))
        # Try editing the original message; if it fails (too old / deleted), send a fresh one
        edited = await edit_msg(client, chat_id, session["message_id"], new_text, reply_markup=new_keyboard)
        if edited is None:
            new_msg = await send_msg(client, chat_id, new_text, reply_markup=new_keyboard)
            session["message_id"] = new_msg.get("message_id", session["message_id"])
        return

    if session:
        warn_text = (
            "⚠️ <b>Ada transaksi yang belum selesai dikonfirmasi!</b>\n\n"
            "Silakan gunakan tombol pada pesan di atas untuk mengkonfirmasi atau membatalkan pencatatan struk tersebut.\n\n"
            "Jika ingin membatalkan, klik tombol <b>Batal</b> pada pesan struk."
        )
        await send_msg(client, chat_id, warn_text)
        return

    # Call the central telegram handler to process text query/addition
    try:
        from packages.api.telegram_handler import handle_telegram_text
        reply = await handle_telegram_text(chat_id, text, user_name)
        await send_msg(client, chat_id, reply)
    except Exception as e:
        logger.exception("Failed to process text message in polling")
        await send_msg(client, chat_id, f"❌ Error processing message: {e}")

# ── Polling loop ──────────────────────────────────────────────────────────────

async def poll():
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in packages/api/.env")
        return

    offset = 0
    logger.info("Starting Telegram polling... Press Ctrl+C to stop.")

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            me = await tg(client, "getMe")
            username = me.get('username', '?')
            print(f"\n[OK] Bot active: @{username} -- send a message or photo to start!\n")
        except Exception as exc:
            print(f"ERROR: Could not reach Telegram API: {exc}")
            return

        while True:
            try:
                resp = await client.get(
                    f"{BASE_URL}/getUpdates",
                    params={"offset": offset, "timeout": 20, "limit": 10},
                    timeout=25
                )
                data = resp.json()
                if not data.get("ok"):
                    err_desc = data.get("description", "Unknown error")
                    sleep_time = 15 if "409" in str(err_desc) or resp.status_code == 409 else 5
                    logger.warning("Telegram getUpdates error (%s): %s — waiting %ss", resp.status_code, err_desc, sleep_time)
                    await asyncio.sleep(sleep_time)
                    continue

                updates = data.get("result", [])

                for upd in updates:
                    offset = upd["update_id"] + 1

                    # Handle Callback Queries
                    cb = upd.get("callback_query")
                    if cb:
                        asyncio.create_task(handle_callback(client, cb))
                        continue

                    # Handle regular Messages
                    msg = upd.get("message")
                    if msg:
                        asyncio.create_task(handle_message(client, msg))

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Poll error: %s — retrying in 3s", exc)
                await asyncio.sleep(3)


def main():
    try:
        asyncio.run(poll())
    except KeyboardInterrupt:
        print("\n[*] Bot stopped.")


if __name__ == "__main__":
    main()
