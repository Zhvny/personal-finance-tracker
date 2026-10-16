import logging
import os
import threading
from pathlib import Path

import httpx

logger = logging.getLogger("core.telegram_notifier")

# Find the project root
try:
    from packages.core.infrastructure.config import Config
    BASE_DIR = Config.BASE_DIR
except ImportError:
    BASE_DIR = Path(__file__).resolve().parents[3]

def get_telegram_config():
    """Loads token and chat id from env or files."""
    # Try environment first
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    # If not in env, check packages/api/.env
    if not token:
        env_path = BASE_DIR / "packages" / "api" / ".env"
        if env_path.exists():
            from dotenv import dotenv_values
            env_vars = dotenv_values(env_path)
            token = env_vars.get("TELEGRAM_BOT_TOKEN")
            if not chat_id:
                chat_id = env_vars.get("TELEGRAM_CHAT_ID")

    # If still no chat_id, check data/telegram_chat_id.txt
    if not chat_id:
        chat_id_path = BASE_DIR / "data" / "telegram_chat_id.txt"
        if chat_id_path.exists():
            try:
                chat_id = chat_id_path.read_text().strip()
            except Exception:
                pass

    return token, chat_id

def send_telegram_notification(text: str, parse_mode: str = "HTML"):
    """
    Sends a telegram message. Runs synchronously in a background thread
    to prevent blocking the main process (CLI/API).
    """
    token, chat_id = get_telegram_config()
    if not token or not chat_id:
        return

    def _send():
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            # Use short timeout to avoid hanging
            with httpx.Client(timeout=5) as client:
                resp = client.post(url, json=payload)
                resp.raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to send telegram notification: {e}")

    threading.Thread(target=_send, daemon=True).start()

async def send_telegram_notification_async(text: str, parse_mode: str = "HTML"):
    """Async version of the notifier."""
    token, chat_id = get_telegram_config()
    if not token or not chat_id:
        return

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
    except Exception as e:
        logger.warning(f"Failed to send async telegram notification: {e}")

async def check_budget_limit_and_alert(category: str, year: int, month: int, expense_repo):
    """
    Checks if the spending for the given category in the given month has exceeded
    80% (warning) or 100% (alert) of the budget limit, and sends a notification.
    """
    try:
        from packages.core.infrastructure.config import Config
        from packages.core.infrastructure.persistence.database import Database

        # 1. Get budget limit for this category
        db_path = Config.get_db_path("budget")
        sql = "SELECT limit_amt FROM budgets WHERE year=? AND month=? AND category=?"
        rows = Database.query(db_path, sql, (year, month, category.lower()))
        if not rows:
            return

        limit = float(rows[0]["limit_amt"])
        if limit <= 0:
            return

        # 2. Get current month's spending for this category
        import inspect
        res = expense_repo.get_monthly_summary(year, month)
        if inspect.isawaitable(res):
            summary = await res
        else:
            summary = res
        by_category = summary.get("by_category", {})
        current_spend = float(by_category.get(category.lower(), 0.0))

        # 3. Check threshold
        pct = (current_spend / limit) * 100
        fmt_spend = f"Rp {current_spend:,.0f}".replace(",", ".")
        fmt_limit = f"Rp {limit:,.0f}".replace(",", ".")

        if current_spend >= limit:
            alert_msg = (
                f"🚨 <b>OVER BUDGET ALERT!</b>\n\n"
                f"Kategori: <b>{category.upper()}</b>\n"
                f"Pengeluaran bulan ini telah melebihi limit!\n"
                f"• Terpakai: <b>{fmt_spend}</b>\n"
                f"• Limit: <b>{fmt_limit}</b>\n"
                f"• Persentase: <b>{pct:.1f}%</b>"
            )
            send_telegram_notification(alert_msg)
        elif current_spend >= limit * 0.8:
            alert_msg = (
                f"⚠️ <b>WARNING: BUDGET HAMPIR HABIS!</b>\n\n"
                f"Kategori: <b>{category.upper()}</b>\n"
                f"Pengeluaran bulan ini mendekati limit (80%+).\n"
                f"• Terpakai: <b>{fmt_spend}</b>\n"
                f"• Limit: <b>{fmt_limit}</b>\n"
                f"• Persentase: <b>{pct:.1f}%</b>"
            )
            send_telegram_notification(alert_msg)
    except Exception as e:
        logger.warning(f"Error checking budget alert: {e}")

