import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from packages.api.backend.routers.deps import dashboard_service, get_active_profile
from packages.core.infrastructure.config import Config

logger = logging.getLogger("api.telegram_handler")

def save_chat_id(chat_id: int):
    try:
        path = Config.BASE_DIR / "data" / "telegram_chat_id.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                if path.read_text().strip() == str(chat_id):
                    return
            except Exception:
                pass
        path.write_text(str(chat_id))
        logger.info(f"Saved active Telegram chat ID: {chat_id}")
    except Exception as e:
        logger.error(f"Failed to save chat ID: {e}")

def parse_amount(val_str: str) -> Optional[float]:
    """Parse Indonesian amount strings like 50k, 1.5jt, Rp 75.000 into float."""
    try:
        # Clean currency prefix
        val_clean = val_str.lower().replace("rp", "").strip()

        if "jt" in val_clean:
            # Strip jt suffix first, then remove thousand-separators that are dots
            num_part = val_clean.replace("jt", "").strip()
            # Replace comma used as decimal separator → dot
            num_part = num_part.replace(",", ".")
            # Strip remaining non-numeric except dot/minus
            num_part = re.sub(r"[^\d.\-]", "", num_part)
            return float(num_part) * 1_000_000
        elif "k" in val_clean or "rb" in val_clean:
            num_part = val_clean.replace("rb", "").replace("k", "").strip()
            num_part = num_part.replace(",", ".").replace(".", "", num_part.count(".") - 1) if num_part.count(".") > 1 else num_part.replace(",", ".")
            num_part = re.sub(r"[^\d.\-]", "", num_part)
            return float(num_part) * 1_000
        else:
            # Plain number — strip thousand-separator dots (only dots followed by 3 digits at end)
            num_part = val_clean.replace(",", "")
            # Remove dots used as thousand separators (keep last one if it's a decimal)
            parts = num_part.split(".")
            if len(parts) > 1:
                if len(parts[-1]) == 3:
                    num_part = "".join(parts)
                else:
                    num_part = "".join(parts[:-1]) + "." + parts[-1]
            else:
                num_part = parts[0]
            num_part = re.sub(r"[^\d.\-]", "", num_part)
            return float(num_part)
    except Exception:
        return None

def detect_category(desc: str, tx_type: str = "expense") -> str:
    desc_lower = desc.lower()
    if tx_type == "expense":
        # simple keyword mapping
        food_keywords = ["makan", "minum", "kopi", "warung", "resto", "food", "cafe", "sushi", "bakso", "nasi"]
        transport_keywords = ["ojek", "bensin", "gojek", "grab", "taxi", "parkir", "tol", "gocar", "train", "kereta"]
        housing_keywords = ["listrik", "air", "sewa", "kos", "kontrakan", "wifi", "internet", "token"]
        ent_keywords = ["nonton", "bioskop", "game", "steam", "netflix", "spotify", "hiburan", "wisata"]
        health_keywords = ["obat", "apotek", "dokter", "sakit", "klinik", "rs", "sehat", "vitamin"]
        shopping_keywords = ["baju", "sepatu", "belanja", "tokopedia", "shopee", "mall", "supermarket", "indomaret", "alfamart"]
        edu_keywords = ["buku", "kursus", "sekolah", "kuliah", "spp", "belajar"]
        invest_keywords = ["saham", "reksadana", "crypto", "emas", "investasi", "bibit"]

        if any(kw in desc_lower for kw in food_keywords): return "food"
        if any(kw in desc_lower for kw in transport_keywords): return "transport"
        if any(kw in desc_lower for kw in housing_keywords): return "housing"
        if any(kw in desc_lower for kw in ent_keywords): return "entertainment"
        if any(kw in desc_lower for kw in health_keywords): return "health"
        if any(kw in desc_lower for kw in shopping_keywords): return "shopping"
        if any(kw in desc_lower for kw in edu_keywords): return "education"
        if any(kw in desc_lower for kw in invest_keywords): return "investment"
        return "other"
    else:
        salary_keywords = ["gaji", "salary", "upah", "payroll"]
        freelance_keywords = ["freelance", "proyek", "project", "side", "klien", "client", "jasadesain"]
        invest_keywords = ["dividen", "kupon", "profit", "saham", "crypto", "bunga"]
        transfer_keywords = ["transfer", "kiriman", "pindahan"]

        if any(kw in desc_lower for kw in salary_keywords): return "salary"
        if any(kw in desc_lower for kw in freelance_keywords): return "freelance"
        if any(kw in desc_lower for kw in invest_keywords): return "investment"
        if any(kw in desc_lower for kw in transfer_keywords): return "transfer"
        return "other"

# ═════════════════════════════════════════════════════════════════════════════
# Phase 5 — Daily / Weekly / Monthly reports (backend-computed from the ledger)
# ═════════════════════════════════════════════════════════════════════════════

_PERIOD_LABELS = {"today": "Hari Ini", "week": "Minggu Ini", "month": "Bulan Ini"}


def _fmt_rp(value) -> str:
    return f"Rp {float(value):,.0f}".replace(",", ".")


def _fmt_pct(value) -> str:
    if value is None:
        return "baru"
    return f"{value:+.0f}%"


def format_report_text(report: dict, profile_id: str) -> str:
    """Render a report dict (from report_service.build_report) as Telegram HTML."""
    label = _PERIOD_LABELS.get(report.get("period"), report.get("period", "?"))
    totals = report["totals"]
    previous = report["previous"]
    comp = report["comparison"]

    lines = [
        f"📊 <b>Laporan {label}</b>",
        f"Profile: <b>{profile_id.upper()}</b>",
        "",
        f"💵 Pemasukan: <b>{_fmt_rp(totals['income'])}</b> "
        f"(vs periode lalu {_fmt_pct(comp['income_pct'])})",
        f"💸 Pengeluaran: <b>{_fmt_rp(totals['expense'])}</b> "
        f"(vs periode lalu {_fmt_pct(comp['expense_pct'])})",
        f"🧮 Net Cashflow: <b>{_fmt_rp(totals['net'])}</b> "
        f"(vs periode lalu {_fmt_pct(comp['net_pct'])})",
        "",
    ]

    if previous["income"] == 0 and previous["expense"] == 0:
        lines.append("<i>Tidak ada transaksi pada periode sebelumnya.</i>\n")

    top_cats = report.get("top_categories") or []
    if top_cats:
        lines.append("🏷️ <b>Top Kategori (Pengeluaran):</b>")
        for c in top_cats:
            lines.append(f" • {c['name']}: {_fmt_rp(c['total'])} ({c['count']}x)")
        lines.append("")

    top_inc = report.get("top_income_categories") or []
    if top_inc:
        lines.append("🏷️ <b>Top Kategori (Pemasukan):</b>")
        for c in top_inc:
            lines.append(f" • {c['name']}: {_fmt_rp(c['total'])} ({c['count']}x)")
        lines.append("")

    top_merch = report.get("top_merchants") or []
    if top_merch:
        lines.append("🏪 <b>Top Merchant:</b>")
        for m in top_merch:
            lines.append(f" • {m['name']}: {_fmt_rp(m['total'])} ({m['count']}x)")
        lines.append("")

    largest = report.get("largest_transactions") or []
    if largest:
        lines.append("💎 <b>Transaksi Terbesar:</b>")
        for t in largest:
            ttype = "⬆️" if t["type"] == "income" else "⬇️"
            d = t.get("date", "")
            if len(d) >= 10:
                d = d[8:10] + "/" + d[5:7]
            lines.append(f" • {ttype} {t['name']}: {_fmt_rp(t['amount'])} ({d})")
        lines.append("")

    trend = report.get("trend") or []
    if trend:
        lines.append("📈 <b>Tren:</b>")
        shown = trend[-7:]  # keep Telegram messages readable
        for b in shown:
            net = b["net"]
            sign = "+" if net >= 0 else "−"
            arrow = "🟢" if net >= 0 else "🔴"
            lines.append(f" • {b['label']}: {arrow} {sign}{_fmt_rp(abs(net))}")
        if len(trend) > len(shown):
            lines.append(f"<i>… dan {len(trend) - len(shown)} periode sebelumnya</i>")

    return "\n".join(lines)


def get_report_text(period: str, profile_id: str) -> str:
    """Compute a period report from the canonical ledger and render it."""
    try:
        from packages.api.backend.finance.report_service import (
            PERIODS,
            ReportError,
            build_report,
        )
        if period not in PERIODS:
            return f"❌ Periode tidak dikenal: {period}. Gunakan <code>report today</code>, <code>week</code>, atau <code>month</code>."
        report = build_report(Config.get_db_path("finance"), period)
    except ReportError as e:
        return f"❌ {e}"
    except Exception as e:
        logger.exception("Report generation failed")
        return f"❌ Gagal mengambil laporan: {e}"
    return format_report_text(report, profile_id)


_REPORT_PERIOD_RE = re.compile(r"^/report\s+(today|week|month)$", re.IGNORECASE)


def _report_period_from_text(text_lower: str) -> Optional[str]:
    """Map a Telegram command/alias to a report period (today|week|month)."""
    if text_lower in ("/daily", "daily", "hari ini", "laporan hari ini",
                      "laporan harian", "report hari ini"):
        return "today"
    if text_lower in ("/weekly", "weekly", "laporan minggu ini",
                      "report minggu ini", "minggu ini"):
        return "week"
    if text_lower in ("/summary", "summary", "laporan", "laporan bulanan",
                      "bulan ini", "/monthly", "monthly", "report",
                      "laporan bulan ini", "report bulan ini"):
        return "month"
    m = _REPORT_PERIOD_RE.match(text_lower)
    if m:
        return m.group(1).lower()
    return None


async def get_monthly_report_text(profile_id: str) -> str:
    return get_report_text("month", profile_id)


async def get_daily_report_text(profile_id: str) -> str:
    return get_report_text("today", profile_id)

async def handle_telegram_text(chat_id: int, text: str, user_name: str) -> str:
    """
    Core handler for all incoming Telegram text messages.
    """
    save_chat_id(chat_id)
    text_clean = text.strip()
    text_lower = text_clean.lower()
    profile_id = get_active_profile()

    # --- Help command ---
    if text_lower in ("/start", "/help", "help", "halo", "hai"):
        return (
            f"🤖 <b>Halo {user_name}! Selamat datang di Finance Tracker Bot.</b>\n\n"
            "Bot ini terhubung dengan database Finance Tracker Anda secara real-time.\n\n"
            "💡 <b>Pesan Teks yang didukung:</b>\n"
            "• Kirim foto struk/kuitansi untuk scan OCR otomatis\n"
            "• Ketik <b>/summary</b> atau <b>laporan</b> untuk melihat keuangan bulan ini\n"
            "• Ketik <b>hari ini</b> atau <b>laporan harian</b> untuk melihat detail hari ini\n"
            "• Ketik <b>minggu ini</b> untuk laporan mingguan\n"
            "• Ketik <b>/report today|week|month</b> untuk laporan lengkap (top kategori, top merchant, tren)\n"
            "• Ketik <b>forecast</b> untuk proyeksi arus kas 30 hari (atau <b>forecast 7</b> untuk 7 hari)\n"
            "• Ketik <b>safetospend</b> untuk berapa yang aman dibelanjakan (atau <b>safetospend 7 5</b> = 7 hari, buffer 5%)\n"
            "• Bisa juga bertanya langsung: <b>berapa saldo saya?</b>, <b>aman belanja berapa?</b>, <b>proyeksi bulan ini</b>, <b>laporan minggu ini</b>, <b>sisa budget</b>, <b>transaksi terakhir</b>\n"
            "• Ketik <b>anomali</b> untuk deteksi kenaikan pengeluaran mencurigakan vs 90 hari sebelumnya\n"
            "• Ketik <b>wawasan</b> untuk ringkasan AI atas data keuanganmu (saldo, tren, budget, anomali)\n"
            "• Ketik <b>skor kesehatan</b> untuk skor 0-100 kesehatan keuanganmu dengan rincian komponen\n"
            "• Ketik <b>kekayaan</b> untuk total kekayaan bersih (kas semua rekening + investasi; transfer tidak mengubah total)\n"
            "• Ketik <b>budget</b> atau <b>limit</b> untuk melihat status budget\n"
            "• Ketik <b>rekening</b> atau <b>saldo</b> untuk sisa saldo virtual pockets\n\n"
            "✍️ <b>Cara Cepat Tambah Transaksi:</b>\n"
            "• <code>tambah pengeluaran 50000 makan siang</code>\n"
            "• <code>tambah pemasukan 1500000 transfer ortu</code>\n"
            "• <code>/expense 35k kopi susu</code>\n"
            "• <code>/income 5jt gaji bulanan</code>\n"
            "• <code>transfer 500rb dari BCA ke Jago</code> untuk pindah dana antar rekening (dengan konfirmasi)"
        )

    # --- Period Reports (Phase 5: today | week | month, backend-computed) ---
    report_period = _report_period_from_text(text_lower)
    if report_period is not None:
        return get_report_text(report_period, profile_id)

    # --- Pockets / Accounts Summary ---
    if text_lower in ("/saldo", "saldo", "rekening", "pocket", "pockets"):
        try:
            summary = await dashboard_service.get_summary(profile_id)
            pockets = summary.get("accounts", {}).get("pockets", [])
            total_balance = summary.get("accounts", {}).get("total_balance", 0)

            def fmt(val):
                return f"Rp {float(val):,.0f}".replace(",", ".")

            text_out = f"🏦 <b>Virtual Accounts / Pockets — {profile_id.upper()}</b>\n"
            text_out += f"Total Saldo: <b>{fmt(total_balance)}</b>\n\n"
            if pockets:
                for p in pockets:
                    text_out += f"• <b>{p['name']}:</b> {fmt(p['balance'])} / {fmt(p['target'])} ({p['progress']:.1f}%)\n"
            else:
                text_out += "Tidak ada virtual accounts aktif."
            return text_out
        except Exception as e:
            return f"❌ Gagal mengambil detail saldo: {e}"

    # --- Cashflow Forecast (Phase 9: deterministic, labeled, transparent) ---
    if text_lower in ("forecast", "prediksi", "proyeksi") or text_lower.startswith("forecast "):
        try:
            from packages.api.backend.finance.forecast_service import (
                ForecastError,
                build_cashflow_forecast,
                format_forecast_text,
            )
            from packages.core.infrastructure.config import Config

            days = 30
            if text_lower.startswith("forecast "):
                try:
                    days = int(text_lower.split()[1])
                except (IndexError, ValueError):
                    days = 30
            result = build_cashflow_forecast(Config.get_db_path("finance"), days=days)
            return format_forecast_text(result)
        except ForecastError as e:
            return f"❌ Proyeksi gagal: {e}"
        except Exception as e:
            return f"❌ Gagal membuat proyeksi: {e}"

    # --- Safe-to-Spend (Phase 10: balance - upcoming outflows - buffer) ---
    if text_lower in ("safetospend", "safe to spend", "aman belanja", "sisa aman") \
            or text_lower.startswith("safetospend "):
        try:
            from packages.api.backend.finance.safe_spend_service import (
                SafeSpendError,
                build_safe_to_spend,
                format_safe_to_spend_text,
            )
            from packages.core.infrastructure.config import Config

            parts = text_lower.split()
            horizon, buffer_pct = "month", 10.0
            if len(parts) >= 2 and parts[1].isdigit():
                horizon = parts[1]
            if len(parts) >= 3 and parts[2].isdigit():
                buffer_pct = float(parts[2])
            result = build_safe_to_spend(
                Config.get_db_path("finance"), horizon=horizon, buffer_pct=buffer_pct
            )
            return format_safe_to_spend_text(result)
        except SafeSpendError as e:
            return f"❌ Aman belanja gagal: {e}"
        except Exception as e:
            return f"❌ Gagal menghitung aman belanja: {e}"

    # --- Net Worth (Phase 15: transfers never change net worth) ---
    if text_lower in ("networth", "net worth", "kekayaan"):
        try:
            from packages.api.backend.finance.net_worth_service import (
                build_net_worth,
                format_net_worth_text,
            )
            from packages.core.infrastructure.config import Config

            result = build_net_worth(
                Config.get_db_path("finance"), Config.get_db_path("investment")
            )
            return format_net_worth_text(result)
        except Exception as e:
            return f"❌ Gagal menghitung kekayaan bersih: {e}"

    # --- Behavioral Health Score (Phase 14: explainable composite 0-100) ---
    if text_lower in ("health", "healthscore", "health score", "skor kesehatan", "sehat"):
        try:
            from packages.api.backend.finance.health_score_service import (
                build_health_score,
                format_health_score_text,
            )
            from packages.core.infrastructure.config import Config

            result = build_health_score(
                Config.get_db_path("finance"), Config.get_db_path("budget")
            )
            return format_health_score_text(result)
        except Exception as e:
            return f"❌ Gagal menghitung skor kesehatan: {e}"

    # --- AI Insights (Phase 13: insight cards from verified backend data only) ---
    if text_lower in ("insights", "wawasan"):
        try:
            from packages.api.backend.finance.insights_service import (
                build_insights,
                format_insights_text,
            )
            from packages.core.infrastructure.config import Config

            result = build_insights(
                Config.get_db_path("finance"), Config.get_db_path("budget")
            )
            return format_insights_text(result)
        except Exception as e:
            return f"❌ Gagal menyusun wawasan: {e}"

    # --- Anomaly Detection (Phase 12: deterministic, explainable rules) ---
    if text_lower in ("anomalies", "anomali", "anomaly", "kejanggalan"):
        try:
            from packages.api.backend.finance.anomaly_service import (
                AnomalyError,
                detect_anomalies,
                format_anomalies_text,
            )
            from packages.core.infrastructure.config import Config

            result = detect_anomalies(Config.get_db_path("finance"))
            return format_anomalies_text(result)
        except AnomalyError as e:
            return f"❌ Deteksi anomali gagal: {e}"
        except Exception as e:
            return f"❌ Gagal mendeteksi anomali: {e}"

    # --- Budget Planner Summary (Phase 6: ledger-backed, configurable thresholds) ---
    if text_lower in ("/budget", "budget", "limit", "sisa budget"):
        try:
            from packages.api.backend.finance.budget_service import build_budget_status
            from packages.core.infrastructure.config import Config

            now = datetime.now()
            status = build_budget_status(
                Config.get_db_path("finance"), Config.get_db_path("budget"), now.year, now.month
            )

            def fmt_budget(val):
                return f"Rp {float(val):,.0f}".replace(",", ".")

            text_out = f"📊 <b>Status Budget Bulan Ini ({now.strftime('%B %Y')})</b>\n\n"
            if not status["categories"]:
                return "📊 Belum ada limit budget yang di-set untuk bulan ini.\n\nKetik <b>budget</b> setelah mengatur limit melalui aplikasi."
            for c in status["categories"]:
                level_emoji = {"ok": "✅", "warn": "⚠️", "alert": "🔶", "over": "🚨"}[c["level"]]
                text_out += (
                    f"{level_emoji} <b>{c['category'].upper()}:</b>\n"
                    f"  Terpakai: {fmt_budget(c['actual'])} / {fmt_budget(c['limit'])}\n"
                    f"  Persentase: {c['pct_used']:.1f}%\n"
                )
            return text_out
        except Exception as e:
            return f"❌ Gagal mengambil status budget: {e}"

    # --- Add Transaction Parsing ---
    add_match = None
    tx_type = None

    prefix_patterns = [
        (r"^(?:tambah\s+)?pengeluaran\s+(\S+)\s+(.+)$", "expense"),
        (r"^(?:tambah\s+)?pemasukan\s+(\S+)\s+(.+)$", "income"),
        (r"^/expense\s+(\S+)\s+(.+)$", "expense"),
        (r"^/income\s+(\S+)\s+(.+)$", "income"),
        (r"^add\s+expense\s+(\S+)\s+(.+)$", "expense"),
        (r"^add\s+income\s+(\S+)\s+(.+)$", "income")
    ]

    for pat, ttype in prefix_patterns:
        m = re.match(pat, text_lower)
        if m:
            add_match = re.match(pat, text_clean)
            tx_type = ttype
            break

    if add_match and tx_type:
        amt_str = add_match.group(1)
        desc = add_match.group(2).strip()

        amount = parse_amount(amt_str)
        if not amount:
            return f"⚠️ Nominal <code>{amt_str}</code> tidak valid. Silakan gunakan angka (contoh: 50000, 50k, 1.5jt)."

        category = detect_category(desc, tx_type)

        try:
            from packages.api.backend.routers.deps import expense_service, income_service

            def fmt(val):
                return f"Rp {float(val):,.0f}".replace(",", ".")

            if tx_type == "expense":
                res = await expense_service.record_expense(
                    amount=amount,
                    description=desc,
                    category=category,
                    payment_method="cash",
                    date=datetime.now()
                )
                return (
                    f"✅ <b>Pengeluaran Berhasil Dicatat!</b>\n\n"
                    f"• <b>Nominal:</b> {fmt(amount)}\n"
                    f"• <b>Deskripsi:</b> {desc}\n"
                    f"• <b>Kategori:</b> {category}\n"
                    f"• <b>Metode:</b> cash"
                )
            else:
                res = await income_service.record_income(
                    amount=amount,
                    source=desc,
                    income_type=category,
                    date=datetime.now(),
                    apply_allocation=True
                )
                return (
                    f"✅ <b>Pemasukan Berhasil Dicatat!</b>\n\n"
                    f"• <b>Nominal:</b> {fmt(amount)}\n"
                    f"• <b>Sumber:</b> {desc}\n"
                    f"• <b>Kategori/Tipe:</b> {category}\n"
                    f"• Smart saving allocation otomatis diterapkan."
                )
        except Exception as e:
            logger.exception("Failed to save text transaction")
            return f"❌ Gagal menyimpan transaksi: {e}"

    return (
        "❓ Pesan tidak dikenali.\n\n"
        "Ketik <b>help</b> untuk melihat format perintah, atau kirim foto struk untuk scan OCR."
    )
