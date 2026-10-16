"""
ai_rule_engine.py — Rule-Based Financial Insight Engine
=========================================================
Fallback AI provider when both Claude API and Ollama are unavailable.
Pure Python, zero external dependencies, bilingual (Bahasa Indonesia + English).

Canonical location : backend/ai/ai_rule_engine.py
Loaded by          : api_server.py via _RULE_ENGINE_PATH (importlib dynamic load)
DO NOT duplicate   : a stale copy previously existed at backend/behavioral/ai_rule_engine.py
                     and has been removed. This file is the single source of truth.

Architecture:
  - Single Responsibility : each analyzer class handles ONE financial aspect.
  - Open/Closed           : add new rules via RuleRegistry without touching callers.
  - Strategy Pattern      : each rule returns a structured dict — composable.
  - DRY                   : all thresholds defined once in THRESHOLDS constant.
  - Zero I/O              : this module never touches disk, DB, or network.

Behavioral Finance theories encoded:
  • Prospect Theory      — losses framed with higher urgency
  • Present Bias         — weekend/impulse flags amplified
  • Mental Accounting    — category risk weights
  • Envelope Budgeting   — category vs budget comparison
  • 50/30/20 Rule        — needs / wants / savings benchmark
  • Emergency Fund Rule  — 3–6 months expense buffer standard
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

# ══════════════════════════════════════════════════════════════════════════════
# § 1  CONSTANTS — Single source of truth
# ══════════════════════════════════════════════════════════════════════════════

THRESHOLDS = {
    # Saving rate bands (%)
    "saving_excellent":  30,
    "saving_good":       20,
    "saving_fair":       10,
    "saving_poor":        5,

    # Impulse index bands (0–1)
    "impulse_high":      0.65,
    "impulse_medium":    0.40,

    # Emergency fund: months of expenses
    "ef_excellent":       6,
    "ef_good":            3,
    "ef_low":             1,

    # Lifestyle inflation: expense growth (%)
    "inflation_severe":  25,
    "inflation_warning": 10,

    # Top category dominance (% of total expense)
    "category_dominant": 45,
    "category_high":     35,

    # Budget overage (%)
    "budget_over":      100,
    "budget_warn":       80,

    # Income diversity: number of sources
    "income_diverse":    3,
    "income_single":     1,
}

# Mental Accounting: category risk weights (1.0 = neutral)
CATEGORY_RISK_WEIGHTS = {
    "entertainment": 1.4,
    "shopping":      1.3,
    "food":          1.1,
    "transport":     0.9,
    "housing":       0.7,
    "health":        0.6,
    "education":     0.5,
    "investment":    0.3,
    "other":         1.0,
}

# 50/30/20 reference: needs / wants / savings
NEEDS_CATEGORIES  = {"housing", "health", "transport", "education"}
WANTS_CATEGORIES  = {"food", "entertainment", "shopping", "other"}


# ══════════════════════════════════════════════════════════════════════════════
# § 2  DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FinancialContext:
    """Aggregated financial data passed into the rule engine."""
    total_income:    float
    total_expense:   float
    income_prev:     float
    expense_prev:    float
    by_category:     Dict[str, float]   # {category: amount}
    budget_limits:   Dict[str, float]   # {category: limit}
    emergency_fund:  float
    month_label:     str
    fbs_score:       Optional[float] = None
    fbs_grade:       Optional[str]   = None
    impulse_index:   Optional[float] = None
    income_sources:  int = 1
    net_worth:       float = 0.0
    top_transactions: List[Dict] = field(default_factory=list)
    # ── Enrichment (v2): personalization + data-driven red flags ───────────────
    profile_name:    str = ""           # e.g. "personal", "pt_kreatif"
    profile_type:    str = ""           # "personal" | "business"
    transfer_income: float = 0.0        # internal transfers excluded from income
    anomalies:       List[Dict] = field(default_factory=list)  # from aggregator
    goals:           List[Dict] = field(default_factory=list)  # savings goals


@dataclass
class RuleResult:
    """Output from a single rule analysis."""
    key:       str            # unique identifier
    severity:  str            # "high" | "medium" | "low" | "positive"
    title_id:  str            # Bahasa Indonesia
    title_en:  str            # English
    body_id:   str            # detailed message (ID)
    body_en:   str            # detailed message (EN)
    action_id: str            # recommended action (ID)
    action_en: str            # recommended action (EN)
    data:      Dict[str, Any] = field(default_factory=dict)  # supporting numbers


# ══════════════════════════════════════════════════════════════════════════════
# § 3  RULE ANALYZERS — Single Responsibility per class
# ══════════════════════════════════════════════════════════════════════════════

class SavingRateAnalyzer:
    """Analyzes saving rate and classifies it into behavioral bands."""

    def analyze(self, ctx: FinancialContext) -> Optional[RuleResult]:
        if ctx.total_income <= 0:
            return None

        rate = (ctx.total_income - ctx.total_expense) / ctx.total_income * 100
        net  = ctx.total_income - ctx.total_expense

        if rate >= THRESHOLDS["saving_excellent"]:
            return RuleResult(
                key="saving_rate", severity="positive",
                title_id="Saving rate sangat baik! 🎉",
                title_en="Excellent saving rate! 🎉",
                body_id=f"Kamu berhasil menabung {rate:.1f}% dari pendapatan bulan ini (Rp {net:,.0f}). Ini jauh di atas benchmark 20%. Terus pertahankan!",
                body_en=f"You saved {rate:.1f}% of this month's income (Rp {net:,.0f}). Well above the 20% benchmark. Keep it up!",
                action_id="Pertimbangkan investasi otomatis untuk uang kelebihan ini.",
                action_en="Consider auto-investing this surplus.",
                data={"rate": rate, "net": net},
            )
        elif rate >= THRESHOLDS["saving_good"]:
            return RuleResult(
                key="saving_rate", severity="low",
                title_id=f"Saving rate oke: {rate:.1f}%",
                title_en=f"Decent saving rate: {rate:.1f}%",
                body_id=f"Kamu menabung Rp {net:,.0f} bulan ini. Masih di atas 20%, tapi ada ruang untuk lebih baik.",
                body_en=f"You saved Rp {net:,.0f} this month. Above 20%, but there's room to improve.",
                action_id="Coba tingkatkan ke 30% dengan memotong 1–2 kategori pengeluaran.",
                action_en="Try pushing toward 30% by trimming 1–2 expense categories.",
                data={"rate": rate, "net": net},
            )
        elif rate >= THRESHOLDS["saving_fair"]:
            return RuleResult(
                key="saving_rate", severity="medium",
                title_id=f"Saving rate rendah: {rate:.1f}%",
                title_en=f"Low saving rate: {rate:.1f}%",
                body_id=f"Kamu hanya menabung {rate:.1f}% bulan ini. Benchmark minimum adalah 20%. Kamu perlu mengurangi pengeluaran atau meningkatkan pendapatan.",
                body_en=f"You only saved {rate:.1f}% this month. The minimum benchmark is 20%. You need to reduce expenses or increase income.",
                action_id="Identifikasi 3 pengeluaran terbesar dan coba kurangi masing-masing 10%.",
                action_en="Identify your top 3 expenses and try reducing each by 10%.",
                data={"rate": rate, "net": net},
            )
        elif rate >= 0:
            return RuleResult(
                key="saving_rate", severity="high",
                title_id=f"Saving rate kritis: {rate:.1f}%",
                title_en=f"Critical saving rate: {rate:.1f}%",
                body_id=f"Kamu hampir tidak menabung bulan ini ({rate:.1f}%). Dengan pola ini, satu kejadian tak terduga bisa merusak keuanganmu.",
                body_en=f"You barely saved anything this month ({rate:.1f}%). At this rate, one unexpected event could derail your finances.",
                action_id="Segera review anggaran dan potong pengeluaran tidak penting minimal 20%.",
                action_en="Immediately review your budget and cut unnecessary expenses by at least 20%.",
                data={"rate": rate, "net": net},
            )
        else:
            deficit = abs(net)
            return RuleResult(
                key="saving_rate", severity="high",
                title_id="⚠️ Pengeluaran melebihi pendapatan!",
                title_en="⚠️ Expenses exceed income!",
                body_id=f"Kamu defisit Rp {deficit:,.0f} bulan ini. Ini situasi tidak berkelanjutan yang harus segera diatasi.",
                body_en=f"You have a deficit of Rp {deficit:,.0f} this month. This is an unsustainable situation that must be addressed immediately.",
                action_id="Stop pengeluaran diskresioner sekarang. Buat rencana darurat untuk menutup defisit.",
                action_en="Stop discretionary spending now. Create an emergency plan to cover the deficit.",
                data={"rate": rate, "net": net, "deficit": deficit},
            )


class LifestyleInflationAnalyzer:
    """Detects lifestyle inflation comparing this month vs last month."""

    def analyze(self, ctx: FinancialContext) -> Optional[RuleResult]:
        if ctx.expense_prev <= 0:
            return None

        pct_chg = (ctx.total_expense - ctx.expense_prev) / ctx.expense_prev * 100
        abs_chg = ctx.total_expense - ctx.expense_prev

        if pct_chg >= THRESHOLDS["inflation_severe"]:
            return RuleResult(
                key="lifestyle_inflation", severity="high",
                title_id=f"⚠️ Lifestyle inflation parah: +{pct_chg:.1f}%",
                title_en=f"⚠️ Severe lifestyle inflation: +{pct_chg:.1f}%",
                body_id=f"Pengeluaranmu naik Rp {abs_chg:,.0f} ({pct_chg:.1f}%) dibanding bulan lalu. Kenaikan >25% adalah tanda lifestyle inflation yang perlu diwaspadai.",
                body_en=f"Your spending jumped Rp {abs_chg:,.0f} ({pct_chg:.1f}%) vs last month. A rise over 25% signals lifestyle inflation that needs attention.",
                action_id="Audit setiap kategori yang naik signifikan. Buat 'spending freeze' selama 2 minggu.",
                action_en="Audit every category that rose significantly. Implement a 2-week spending freeze.",
                data={"pct_chg": pct_chg, "abs_chg": abs_chg},
            )
        elif pct_chg >= THRESHOLDS["inflation_warning"]:
            return RuleResult(
                key="lifestyle_inflation", severity="medium",
                title_id=f"Pengeluaran naik {pct_chg:.1f}% vs bulan lalu",
                title_en=f"Expenses up {pct_chg:.1f}% vs last month",
                body_id=f"Pengeluaranmu meningkat Rp {abs_chg:,.0f}. Pastikan ini bukan kebiasaan, dan ada alasan yang jelas untuk kenaikan ini.",
                body_en=f"Spending increased by Rp {abs_chg:,.0f}. Ensure this isn't habit creep and there's a clear reason for the increase.",
                action_id="Cek kategori mana yang naik paling besar dan evaluasi apakah perlu.",
                action_en="Check which categories increased most and evaluate if they're necessary.",
                data={"pct_chg": pct_chg, "abs_chg": abs_chg},
            )
        elif pct_chg <= -THRESHOLDS["inflation_warning"]:
            return RuleResult(
                key="lifestyle_inflation", severity="positive",
                title_id=f"Pengeluaran turun {abs(pct_chg):.1f}% 👍",
                title_en=f"Expenses down {abs(pct_chg):.1f}% 👍",
                body_id=f"Kamu berhasil mengurangi pengeluaran Rp {abs(abs_chg):,.0f} dibanding bulan lalu. Ini pencapaian luar biasa!",
                body_en=f"You reduced spending by Rp {abs(abs_chg):,.0f} vs last month. Outstanding achievement!",
                action_id="Pertahankan pola ini. Alokasikan penghematan ke investasi atau dana darurat.",
                action_en="Maintain this pattern. Allocate the savings to investments or emergency fund.",
                data={"pct_chg": pct_chg, "abs_chg": abs_chg},
            )
        return None


class CategoryConcentrationAnalyzer:
    """Detects over-concentration in high-risk spending categories."""

    def analyze(self, ctx: FinancialContext) -> Optional[RuleResult]:
        if ctx.total_expense <= 0 or not ctx.by_category:
            return None

        results = []
        for cat, amt in ctx.by_category.items():
            pct    = amt / ctx.total_expense * 100
            weight = CATEGORY_RISK_WEIGHTS.get(cat, 1.0)

            if pct >= THRESHOLDS["category_dominant"] and weight >= 1.0:
                results.append(RuleResult(
                    key=f"category_concentration_{cat}", severity="high",
                    title_id=f"{cat.title()} dominasi {pct:.1f}% pengeluaran",
                    title_en=f"{cat.title()} dominates {pct:.1f}% of spending",
                    body_id=f"Kategori {cat} menyedot Rp {amt:,.0f} ({pct:.1f}% dari total). Dominasi >40% pada kategori berisiko tinggi perlu dievaluasi.",
                    body_en=f"Category '{cat}' consumed Rp {amt:,.0f} ({pct:.1f}% of total). Dominance >40% in a high-risk category warrants review.",
                    action_id=f"Set batas bulanan untuk {cat} dan patuhi dengan ketat.",
                    action_en=f"Set a monthly cap for '{cat}' and stick to it strictly.",
                    data={"category": cat, "amount": amt, "pct": pct},
                ))
            elif pct >= THRESHOLDS["category_high"] and weight >= 1.3:
                results.append(RuleResult(
                    key=f"category_concentration_{cat}", severity="medium",
                    title_id=f"{cat.title()} tinggi: {pct:.1f}% pengeluaran",
                    title_en=f"{cat.title()} high: {pct:.1f}% of spending",
                    body_id=f"Rp {amt:,.0f} di {cat} ({pct:.1f}%). Pertimbangkan apakah ini sesuai prioritas keuanganmu.",
                    body_en=f"Rp {amt:,.0f} on {cat} ({pct:.1f}%). Consider whether this aligns with your financial priorities.",
                    action_id=f"Kurangi {cat} 15–20% bulan depan.",
                    action_en=f"Reduce '{cat}' by 15–20% next month.",
                    data={"category": cat, "amount": amt, "pct": pct},
                ))
        # Return highest severity result
        if results:
            results.sort(key=lambda r: ["positive", "low", "medium", "high"].index(r.severity), reverse=True)
            return results[0]
        return None


class BudgetAdherenceAnalyzer:
    """Checks spending vs user-set budget limits."""

    def analyze(self, ctx: FinancialContext) -> Optional[RuleResult]:
        if not ctx.budget_limits:
            return None

        over_cats    = []
        warning_cats = []

        for cat, limit in ctx.budget_limits.items():
            if limit <= 0:
                continue
            actual = ctx.by_category.get(cat, 0)
            pct    = actual / limit * 100
            if pct >= THRESHOLDS["budget_over"]:
                over_cats.append((cat, actual, limit, pct))
            elif pct >= THRESHOLDS["budget_warn"]:
                warning_cats.append((cat, actual, limit, pct))

        if over_cats:
            cats_str_id = ", ".join(f"{c[0]} ({c[3]:.0f}%)" for c in over_cats[:3])
            cats_str_en = ", ".join(f"{c[0]} ({c[3]:.0f}%)" for c in over_cats[:3])
            return RuleResult(
                key="budget_over", severity="high",
                title_id=f"Budget terlampaui: {cats_str_id}",
                title_en=f"Budget exceeded: {cats_str_en}",
                body_id=f"{len(over_cats)} kategori melebihi batas budget yang ditetapkan. Ini menunjukkan kurangnya disiplin anggaran.",
                body_en=f"{len(over_cats)} categories exceeded their budget limits. This indicates a lack of budget discipline.",
                action_id="Review pengeluaran di kategori tersebut dan buat komitmen tertulis untuk bulan depan.",
                action_en="Review spending in those categories and make a written commitment for next month.",
                data={"over_categories": over_cats, "warning_categories": warning_cats},
            )
        elif warning_cats:
            cats_str = ", ".join(c[0] for c in warning_cats[:3])
            return RuleResult(
                key="budget_warning", severity="medium",
                title_id=f"Budget hampir habis: {cats_str}",
                title_en=f"Budget nearly exhausted: {cats_str}",
                body_id=f"{len(warning_cats)} kategori sudah di atas 80% batas budget. Hati-hati pengeluaran tersisa bulan ini.",
                body_en=f"{len(warning_cats)} categories are above 80% of their budget limit. Be careful with remaining spending this month.",
                action_id="Tunda pembelian tidak penting di kategori ini hingga bulan depan.",
                action_en="Postpone non-essential purchases in these categories until next month.",
                data={"warning_categories": warning_cats},
            )
        else:
            return RuleResult(
                key="budget_on_track", severity="positive",
                title_id="Semua kategori dalam batas budget ✓",
                title_en="All categories within budget ✓",
                body_id="Budget bulan ini terkontrol dengan baik. Disiplin finansial yang bagus!",
                body_en="This month's budget is well-controlled. Great financial discipline!",
                action_id="Pertahankan pola ini dan review budget setiap awal bulan.",
                action_en="Maintain this pattern and review your budget at the start of each month.",
                data={},
            )


class EmergencyFundAnalyzer:
    """Evaluates emergency fund adequacy (3–6 month rule)."""

    def analyze(self, ctx: FinancialContext) -> Optional[RuleResult]:
        if ctx.total_expense <= 0:
            return None

        # Use average of this month and last month for stability
        avg_exp = (ctx.total_expense + ctx.expense_prev) / 2 if ctx.expense_prev > 0 else ctx.total_expense
        months_covered = ctx.emergency_fund / avg_exp if avg_exp > 0 else 0

        if months_covered >= THRESHOLDS["ef_excellent"]:
            return RuleResult(
                key="emergency_fund", severity="positive",
                title_id=f"Dana darurat solid: {months_covered:.1f} bulan 💪",
                title_en=f"Emergency fund solid: {months_covered:.1f} months 💪",
                body_id=f"Dana daruratmu (Rp {ctx.emergency_fund:,.0f}) mencukupi {months_covered:.1f} bulan pengeluaran. Di atas standar 6 bulan.",
                body_en=f"Your emergency fund (Rp {ctx.emergency_fund:,.0f}) covers {months_covered:.1f} months of expenses. Above the 6-month standard.",
                action_id="Dana darurat aman. Fokuskan sisa cash ke investasi produktif.",
                action_en="Emergency fund is secure. Focus remaining cash on productive investments.",
                data={"months_covered": months_covered, "amount": ctx.emergency_fund},
            )
        elif months_covered >= THRESHOLDS["ef_good"]:
            gap = (THRESHOLDS["ef_excellent"] * avg_exp) - ctx.emergency_fund
            return RuleResult(
                key="emergency_fund", severity="low",
                title_id=f"Dana darurat: {months_covered:.1f} bulan (target 6 bulan)",
                title_en=f"Emergency fund: {months_covered:.1f} months (target: 6 months)",
                body_id=f"Dana daruratmu memenuhi standar minimum (3 bulan). Butuh Rp {gap:,.0f} lagi untuk mencapai target ideal 6 bulan.",
                body_en=f"Your emergency fund meets the minimum standard (3 months). Need Rp {gap:,.0f} more to reach the ideal 6-month target.",
                action_id=f"Tambahkan Rp {gap/6:,.0f}/bulan ke dana darurat selama 6 bulan ke depan.",
                action_en=f"Add Rp {gap/6:,.0f}/month to your emergency fund over the next 6 months.",
                data={"months_covered": months_covered, "gap": gap},
            )
        elif months_covered >= THRESHOLDS["ef_low"]:
            gap = (THRESHOLDS["ef_good"] * avg_exp) - ctx.emergency_fund
            return RuleResult(
                key="emergency_fund", severity="medium",
                title_id=f"⚠️ Dana darurat rendah: {months_covered:.1f} bulan",
                title_en=f"⚠️ Low emergency fund: {months_covered:.1f} months",
                body_id=f"Dana daruratmu hanya cukup untuk {months_covered:.1f} bulan. Standar minimum adalah 3 bulan. Butuh Rp {gap:,.0f} lagi.",
                body_en=f"Your emergency fund only covers {months_covered:.1f} months. The minimum standard is 3 months. Need Rp {gap:,.0f} more.",
                action_id="Prioritaskan mengisi dana darurat sebelum investasi apapun.",
                action_en="Prioritize filling the emergency fund before any investments.",
                data={"months_covered": months_covered, "gap": gap},
            )
        else:
            needed = THRESHOLDS["ef_good"] * avg_exp
            return RuleResult(
                key="emergency_fund", severity="high",
                title_id="🚨 Dana darurat tidak memadai!",
                title_en="🚨 Emergency fund critically low!",
                body_id=f"Dana darurat Rp {ctx.emergency_fund:,.0f} hanya {months_covered:.1f} bulan. Satu krisis bisa membuat keuanganmu hancur. Target minimum: Rp {needed:,.0f}.",
                body_en=f"Emergency fund Rp {ctx.emergency_fund:,.0f} is only {months_covered:.1f} months. One crisis could devastate your finances. Minimum target: Rp {needed:,.0f}.",
                action_id="Buat target menabung KHUSUS untuk dana darurat. Ini prioritas #1.",
                action_en="Create a DEDICATED savings goal for the emergency fund. This is priority #1.",
                data={"months_covered": months_covered, "needed": needed},
            )


class IncomeDiversificationAnalyzer:
    """Analyzes income source diversity and income growth."""

    def analyze(self, ctx: FinancialContext) -> Optional[RuleResult]:
        sources = ctx.income_sources

        if ctx.income_prev > 0:
            inc_growth = (ctx.total_income - ctx.income_prev) / ctx.income_prev * 100
        else:
            inc_growth = 0

        if sources >= THRESHOLDS["income_diverse"]:
            return RuleResult(
                key="income_diversity", severity="positive",
                title_id=f"Pendapatan terdiversifikasi: {sources} sumber",
                title_en=f"Diversified income: {sources} sources",
                body_id=f"Kamu memiliki {sources} sumber pendapatan. Diversifikasi mengurangi risiko finansial secara signifikan.",
                body_en=f"You have {sources} income sources. Diversification significantly reduces financial risk.",
                action_id="Pertimbangkan untuk menginvestasikan pendapatan tambahan agar lebih pasif.",
                action_en="Consider investing extra income for more passive streams.",
                data={"sources": sources, "growth": inc_growth},
            )
        elif sources == THRESHOLDS["income_single"]:
            return RuleResult(
                key="income_diversity", severity="medium",
                title_id="Satu sumber pendapatan — risiko tinggi",
                title_en="Single income source — high risk",
                body_id="Pendapatanmu hanya dari satu sumber. Ini menciptakan kerentanan finansial besar. Jika sumber ini hilang, kamu tidak punya backup.",
                body_en="You have only one income source. This creates significant financial vulnerability. If this source disappears, you have no backup.",
                action_id="Mulai kembangkan side income: freelance, konten digital, atau investasi passive.",
                action_en="Start developing side income: freelance, digital content, or passive investments.",
                data={"sources": sources, "growth": inc_growth},
            )
        return None


class ImpulseSpendingAnalyzer:
    """Detects impulse spending patterns from impulse_index."""

    def analyze(self, ctx: FinancialContext) -> Optional[RuleResult]:
        if ctx.impulse_index is None:
            return None

        idx = ctx.impulse_index

        if idx >= THRESHOLDS["impulse_high"]:
            return RuleResult(
                key="impulse_spending", severity="high",
                title_id=f"Impulse spending tinggi (indeks: {idx:.2f})",
                title_en=f"High impulse spending (index: {idx:.2f})",
                body_id=f"Indeks impulsivitasmu {idx:.2f}/1.0. Ini menunjukkan banyak pembelian tidak terencana yang mengikis kemampuan menabung.",
                body_en=f"Your impulsivity index is {idx:.2f}/1.0. This indicates many unplanned purchases that erode your saving ability.",
                action_id="Terapkan aturan 48 jam: tunggu 2 hari sebelum setiap pembelian >Rp 200.000.",
                action_en="Apply the 48-hour rule: wait 2 days before any purchase over Rp 200,000.",
                data={"impulse_index": idx},
            )
        elif idx >= THRESHOLDS["impulse_medium"]:
            return RuleResult(
                key="impulse_spending", severity="medium",
                title_id=f"Impulse spending sedang (indeks: {idx:.2f})",
                title_en=f"Moderate impulse spending (index: {idx:.2f})",
                body_id="Ada beberapa pola pembelian impulsif terdeteksi. Masih bisa dikendalikan dengan disiplin.",
                body_en="Some impulsive purchasing patterns detected. Still manageable with discipline.",
                action_id="Buat wish list dan review setiap minggu sebelum membeli.",
                action_en="Create a wish list and review it weekly before purchasing.",
                data={"impulse_index": idx},
            )
        else:
            return RuleResult(
                key="impulse_spending", severity="positive",
                title_id=f"Pembelian terencana dengan baik ✓ (indeks: {idx:.2f})",
                title_en=f"Well-planned purchases ✓ (index: {idx:.2f})",
                body_id="Sebagian besar pengeluaranmu terencana dan rasional. Ini tanda kontrol keuangan yang matang.",
                body_en="Most of your spending is planned and rational. This reflects mature financial control.",
                action_id="Pertahankan kebiasaan baik ini. Review anggaran bulanan secara rutin.",
                action_en="Maintain this good habit. Review your budget regularly.",
                data={"impulse_index": idx},
            )


class AnomalyAnalyzer:
    """
    Surfaces the explicit anomaly flags computed by the data aggregator:
    deficit, income drop, transfer-heavy inflows, category spikes, and large
    single transactions. These are concrete, data-driven red flags that keep
    the assessment honest about the real situation.
    """

    _PRIORITY = ["deficit", "income_drop", "transfer_heavy", "concentration", "category_spike"]

    def analyze(self, ctx: FinancialContext) -> Optional[RuleResult]:
        if not ctx.anomalies:
            return None

        known = {a.get("type") for a in ctx.anomalies}
        results = []
        for atype in self._PRIORITY:
            if atype not in known:
                continue
            msg = next((a.get("message", "") for a in ctx.anomalies if a.get("type") == atype), "")

            if atype == "deficit":
                results.append(RuleResult(
                    key="anomaly_deficit", severity="high",
                    title_id="Defisit bulan ini",
                    title_en="Monthly deficit detected",
                    body_id=msg or "Pengeluaran bulan ini melebihi pemasukan.",
                    body_en=msg or "This month's expenses exceeded income.",
                    action_id="Tutup defisit sekarang: hentikan pengeluaran diskresioner dan tarik dana dari pos lain untuk menutup selisih bulan ini.",
                    action_en="Close the gap now: pause discretionary spending and pull from other buckets to cover this month's shortfall.",
                    data={"type": atype},
                ))
            elif atype == "income_drop":
                results.append(RuleResult(
                    key="anomaly_income_drop", severity="high",
                    title_id="Pemasukan riil turun tajam",
                    title_en="Real income dropped sharply",
                    body_id=msg or "Pemasukan riil bulan ini jauh di bawah bulan lalu.",
                    body_en=msg or "Real income this month is well below last month.",
                    action_id="Cari penyebab penurunan pemasukan dan sesuaikan rencana pengeluaran dengan arus kas yang ada.",
                    action_en="Find the cause of the income drop and align spending plans with the actual cash flow.",
                    data={"type": atype},
                ))
            elif atype == "transfer_heavy":
                results.append(RuleResult(
                    key="anomaly_transfer_heavy", severity="medium",
                    title_id="Banyak transfer masuk — bukan pemasukan riil",
                    title_en="Large inflows are transfers, not real income",
                    body_id=msg or "Sebagian besar arus masuk bulan ini berasal dari pemindahan dana antar rekening.",
                    body_en=msg or "Most of this month's inflows came from internal transfers between accounts.",
                    action_id="Jangan jadikan transfer sebagai acuan penghasilan. Evaluasi pendapatan riil dari aktivitas, bukan perpindahan dana.",
                    action_en="Don't treat transfers as earnings. Assess real income from activity, not money movements.",
                    data={"type": atype},
                ))
            elif atype == "concentration":
                results.append(RuleResult(
                    key="anomaly_concentration", severity="medium",
                    title_id="Transaksi besar mendominasi pengeluaran",
                    title_en="One large transaction dominates spending",
                    body_id=msg or "Ada transaksi tunggal yang mendominasi total pengeluaran bulan ini.",
                    body_en=msg or "A single transaction dominates this month's total spending.",
                    action_id="Pisahkan pengeluaran besar (tagihan tahunan/aset) dari pengeluaran rutin agar analisis lebih akurat.",
                    action_en="Separate lump payments (annual bills/assets) from routine spending for a more accurate analysis.",
                    data={"type": atype},
                ))
            elif atype == "category_spike":
                results.append(RuleResult(
                    key="anomaly_category_spike", severity="low",
                    title_id="Lonjakan pengeluaran per kategori",
                    title_en="Category spending spike",
                    body_id=msg or "Ada kategori yang pengeluarannya melonjak signifikan bulan ini.",
                    body_en=msg or "A category saw a significant spending jump this month.",
                    action_id="Pastikan lonjakan ini memang direncanakan, bukan kebocoran anggaran.",
                    action_en="Confirm the spike was planned and not a budget leak.",
                    data={"type": atype},
                ))

        if results:
            results.sort(key=lambda r: ["low", "medium", "high"].index(r.severity), reverse=True)
            return results[0]
        return None


class GoalProgressAnalyzer:
    """
    Highlights the nearest savings goal with a deadline. A goal due soon but
    underfunded becomes a concrete, personal action item; a fully-funded goal
    becomes a positive reinforcement.
    """

    def analyze(self, ctx: FinancialContext) -> Optional[RuleResult]:
        if not ctx.goals:
            return None

        today = datetime.now().date()
        active = []
        for g in ctx.goals:
            target   = g.get("target_amount") or 0
            current  = g.get("current_amount") or 0
            deadline = g.get("target_date")
            try:
                if isinstance(deadline, datetime):
                    due = deadline.date()
                elif isinstance(deadline, str) and deadline:
                    due = datetime.strptime(deadline[:10], "%Y-%m-%d").date()
                else:
                    continue
            except Exception:
                continue
            active.append({
                "name":      g.get("name") or "Goal",
                "target":    float(target),
                "current":   float(current),
                "due":       due,
                "days_left": (due - today).days,
            })

        if not active:
            return None

        active.sort(key=lambda g: (g["days_left"] >= 0, g["days_left"] if g["days_left"] >= 0 else 10**9))
        g        = active[0]
        missing  = max(0.0, g["target"] - g["current"])
        pct      = (g["current"] / g["target"] * 100) if g["target"] > 0 else 100.0
        name     = g["name"]

        if g["days_left"] < 0:
            return RuleResult(
                key="goal_progress", severity="medium",
                title_id=f"Goal '{name}' sudah lewat tanggal target",
                title_en=f"Goal '{name}' passed its target date",
                body_id=f"Goal '{name}' (target Rp {g['target']:,.0f}) baru terkumpul Rp {g['current']:,.0f} ({pct:.0f}%). Deadline sudah lewat.",
                body_en=f"Goal '{name}' (target Rp {g['target']:,.0f}) has Rp {g['current']:,.0f} saved ({pct:.0f}%). The deadline has passed.",
                action_id="Perpanjang target atau pecah menjadi target bulanan yang lebih kecil dan realistis.",
                action_en="Extend the target or split it into smaller, realistic monthly targets.",
                data={"goal": name, "pct": pct},
            )
        if g["days_left"] <= 30 and missing > 0:
            per_month = missing / max(1, g["days_left"] / 30)
            return RuleResult(
                key="goal_progress", severity="high",
                title_id=f"Goal '{name}' jatuh tempo {g['days_left']} hari lagi",
                title_en=f"Goal '{name}' due in {g['days_left']} days",
                body_id=f"Goal '{name}' butuh Rp {missing:,.0f} lagi ({pct:.0f}%) dalam {g['days_left']} hari. Butuh sekitar Rp {per_month:,.0f}/bulan untuk tepat waktu.",
                body_en=f"Goal '{name}' needs Rp {missing:,.0f} more ({pct:.0f}%) within {g['days_left']} days. That's about Rp {per_month:,.0f}/month to stay on track.",
                action_id=f"Prioritaskan menabung untuk '{name}' — kurangi sementara kategori pengeluaran terbesar.",
                action_en=f"Prioritize saving for '{name}' — temporarily trim the biggest expense category.",
                data={"goal": name, "missing": missing, "days_left": g["days_left"]},
            )
        if missing <= 0:
            return RuleResult(
                key="goal_progress", severity="positive",
                title_id=f"Goal '{name}' tercapai!",
                title_en=f"Goal '{name}' reached!",
                body_id=f"Goal '{name}' sudah terkumpul penuh Rp {g['current']:,.0f}. Tepat waktu dan konsisten.",
                body_en=f"Goal '{name}' is fully funded at Rp {g['current']:,.0f}. On time and consistent.",
                action_id="Rencanakan goal berikutnya dan nikmati pencapaian ini.",
                action_en="Plan the next goal and enjoy this achievement.",
                data={"goal": name, "pct": 100.0},
            )
        return RuleResult(
            key="goal_progress", severity="low",
            title_id=f"Goal '{name}' terdekat: {pct:.0f}% terkumpul",
            title_en=f"Nearest goal '{name}': {pct:.0f}% funded",
            body_id=f"Goal '{name}' tinggal {g['days_left']} hari lagi, sudah terkumpul Rp {g['current']:,.0f} dari Rp {g['target']:,.0f} ({pct:.0f}%).",
            body_en=f"Goal '{name}' is due in {g['days_left']} days, with Rp {g['current']:,.0f} of Rp {g['target']:,.0f} saved ({pct:.0f}%).",
            action_id="Tetap konsisten menabung dan jangan lupa sisihkan dana darurat.",
            action_en="Stay consistent and don't forget to keep the emergency fund topped up.",
            data={"goal": name, "pct": pct, "days_left": g["days_left"]},
        )


# ══════════════════════════════════════════════════════════════════════════════
# § 4  INSIGHT COMPOSER — Assembles rule results into structured output
# ══════════════════════════════════════════════════════════════════════════════

class InsightComposer:
    """
    Composes individual rule results into a unified insight payload.
    Output schema mirrors Claude/Ollama response for drop-in compatibility.
    """

    _ANALYZERS = [
        AnomalyAnalyzer(),
        SavingRateAnalyzer(),
        LifestyleInflationAnalyzer(),
        CategoryConcentrationAnalyzer(),
        BudgetAdherenceAnalyzer(),
        EmergencyFundAnalyzer(),
        IncomeDiversificationAnalyzer(),
        ImpulseSpendingAnalyzer(),
        GoalProgressAnalyzer(),
    ]

    def compose(self, ctx: FinancialContext) -> Dict[str, Any]:
        results: List[RuleResult] = []
        for analyzer in self._ANALYZERS:
            try:
                result = analyzer.analyze(ctx)
                if result:
                    results.append(result)
            except Exception:
                pass  # Individual rule failure must never break the whole engine

        highs    = [r for r in results if r.severity == "high"]
        mediums  = [r for r in results if r.severity == "medium"]
        positives = [r for r in results if r.severity == "positive"]
        lows     = [r for r in results if r.severity == "low"]

        # ── Overall assessment ────────────────────────────────────────────────
        profile_ref = f"profil '{ctx.profile_name}' " if ctx.profile_name else ""
        if highs:
            assessment_id = f"Kondisi keuangan {profile_ref}{ctx.month_label} memerlukan perhatian serius. Ada {len(highs)} risiko utama yang perlu segera diatasi."
            assessment_en = f"Finances for profile '{ctx.profile_name}' in {ctx.month_label} require serious attention. There are {len(highs)} major risks to address immediately." if ctx.profile_name else f"Financial condition in {ctx.month_label} requires serious attention. There are {len(highs)} major risks to address immediately."
        elif mediums:
            assessment_id = f"Keuangan {profile_ref}bulan {ctx.month_label} cukup baik tapi ada beberapa area yang perlu diperbaiki."
            assessment_en = f"Finances for profile '{ctx.profile_name}' in {ctx.month_label} are fair but several areas need improvement." if ctx.profile_name else f"Finances in {ctx.month_label} are fair but several areas need improvement."
        elif positives:
            assessment_id = f"Keuangan {profile_ref}{ctx.month_label} dalam kondisi baik! Beberapa pencapaian patut diapresiasi."
            assessment_en = f"Finances for profile '{ctx.profile_name}' in {ctx.month_label} are in good shape! Several achievements worth appreciating." if ctx.profile_name else f"Finances in {ctx.month_label} are in good shape! Several achievements worth appreciating."
        else:
            assessment_id = f"Data keuangan {profile_ref}{ctx.month_label} menunjukkan kondisi yang stabil."
            assessment_en = f"Financial data for {ctx.month_label} shows stable conditions."

        # ── Top risk ──────────────────────────────────────────────────────────
        top_risk_id = highs[0].body_id if highs else (mediums[0].body_id if mediums else "Tidak ada risiko signifikan terdeteksi.")
        top_risk_en = highs[0].body_en if highs else (mediums[0].body_en if mediums else "No significant risks detected.")

        # ── Biggest win ───────────────────────────────────────────────────────
        biggest_win_id = positives[0].body_id if positives else None
        biggest_win_en = positives[0].body_en if positives else None

        # ── Spending pattern ──────────────────────────────────────────────────
        if ctx.by_category and ctx.total_expense > 0:
            top_cats = sorted(ctx.by_category.items(), key=lambda x: x[1], reverse=True)[:3]
            cat_list_id = ", ".join(f"{c} ({v/ctx.total_expense*100:.1f}%)" for c, v in top_cats)
            cat_list_en = ", ".join(f"{c} ({v/ctx.total_expense*100:.1f}%)" for c, v in top_cats)
            spending_pattern_id = f"Pengeluaran terkonsentrasi di: {cat_list_id}."
            spending_pattern_en = f"Spending concentrated in: {cat_list_en}."
        else:
            spending_pattern_id = "Tidak ada data pengeluaran bulan ini."
            spending_pattern_en = "No spending data for this month."

        # ── Impulse analysis ──────────────────────────────────────────────────
        impulse_result = next((r for r in results if r.key == "impulse_spending"), None)
        impulse_id = impulse_result.body_id if impulse_result else "Data impulse tidak tersedia."
        impulse_en = impulse_result.body_en if impulse_result else "Impulse data not available."

        # ── Lifestyle inflation verdict ───────────────────────────────────────
        inflation_result = next((r for r in results if r.key == "lifestyle_inflation"), None)
        if inflation_result:
            inflation_id = f"{inflation_result.title_id}. {inflation_result.body_id}"
            inflation_en = f"{inflation_result.title_en}. {inflation_result.body_en}"
        else:
            inflation_id = "Perubahan pengeluaran bulan ini dalam batas normal."
            inflation_en = "This month's spending change is within normal bounds."

        # ── Recommendations (top 3, highest severity first) ───────────────────
        ordered = highs + mediums + lows + positives
        recs = []
        for r in ordered[:3]:
            priority = "high" if r.severity == "high" else "medium" if r.severity == "medium" else "low"
            recs.append({
                "priority": priority,
                "action":   r.action_id,
                "action_en": r.action_en,
                "reason":   r.body_id,
                "reason_en": r.body_en,
                "impact":   _impact_for(r.key),
            })

        # ── Next month forecast ───────────────────────────────────────────────
        if ctx.total_income > 0:
            proj_savings = ctx.total_income - ctx.total_expense
            if proj_savings > 0:
                forecast_id = f"Jika pola ini berlanjut, kamu akan menabung sekitar Rp {proj_savings:,.0f} bulan depan."
                forecast_en = f"If this pattern continues, you'll save about Rp {proj_savings:,.0f} next month."
            else:
                forecast_id = "Jika pola ini berlanjut, kamu berisiko defisit lagi bulan depan. Segera ambil tindakan."
                forecast_en = "If this pattern continues, you risk another deficit next month. Take action now."
        else:
            forecast_id = "Tambahkan data pendapatan untuk melihat proyeksi bulan depan."
            forecast_en = "Add income data to see next month's projection."

        # ── Motivational note ─────────────────────────────────────────────────
        motivational_id = _pick_motivation(ctx, results)
        motivational_en = _pick_motivation_en(ctx, results)

        # ── Score interpretation ──────────────────────────────────────────────
        if ctx.fbs_score is not None:
            score_interp_id = f"Skor FBS {ctx.fbs_score:.0f}/100 ({ctx.fbs_grade or '?'}) — {_grade_label_id(ctx.fbs_grade)}."
            score_interp_en = f"FBS score {ctx.fbs_score:.0f}/100 ({ctx.fbs_grade or '?'}) — {_grade_label_en(ctx.fbs_grade)}."
        else:
            score_interp_id = "Skor FBS dihitung dari saving rate, impulse control, konsistensi, dan dana darurat."
            score_interp_en = "FBS score is computed from saving rate, impulse control, consistency, and emergency fund."

        return {
            "overall_assessment":           assessment_id,
            "overall_assessment_en":        assessment_en,
            "score_interpretation":         score_interp_id,
            "score_interpretation_en":      score_interp_en,
            "top_risk":                     top_risk_id,
            "top_risk_en":                  top_risk_en,
            "biggest_win":                  biggest_win_id,
            "biggest_win_en":               biggest_win_en,
            "spending_pattern":             spending_pattern_id,
            "spending_pattern_en":          spending_pattern_en,
            "impulse_analysis":             impulse_id,
            "impulse_analysis_en":          impulse_en,
            "lifestyle_inflation_verdict":  inflation_id,
            "lifestyle_inflation_verdict_en": inflation_en,
            "recommendations":              recs,
            "next_month_forecast":          forecast_id,
            "next_month_forecast_en":       forecast_en,
            "motivational_note":            motivational_id,
            "motivational_note_en":         motivational_en,
            # Debug: all rule results
            "_rule_results": [
                {"key": r.key, "severity": r.severity, "title": r.title_id}
                for r in results
            ],
            # Machine-readable snapshot for the frontend / debugging
            "data_snapshot": {
                "month_label":     ctx.month_label,
                "profile_name":    ctx.profile_name,
                "profile_type":    ctx.profile_type,
                "total_income":    ctx.total_income,
                "total_expense":   ctx.total_expense,
                "net":             ctx.total_income - ctx.total_expense,
                "transfer_income": ctx.transfer_income,
                "saving_rate_pct": ((ctx.total_income - ctx.total_expense) / ctx.total_income * 100) if ctx.total_income > 0 else 0.0,
                "anomalies":       ctx.anomalies,
                "goals":           ctx.goals,
            },
        }


# ══════════════════════════════════════════════════════════════════════════════
# § 5  RECEIPT PARSER — moved to backend/ai/receipt_parser.py (R1 refactor, 2026-09-05)
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# § 6  HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _impact_for(key: str) -> str:
    IMPACTS = {
        "saving_rate":             "Meningkatkan saving rate 10% = Rp 120.000+ ekstra per tahun per juta pendapatan.",
        "lifestyle_inflation":     "Memotong lifestyle inflation bisa menambah tabungan 15–25% lebih banyak.",
        "category_concentration":  "Mendiversifikasi pengeluaran mengurangi financial stress secara signifikan.",
        "budget_over":             "Mematuhi budget bisa menghemat 10–20% dari total pengeluaran.",
        "budget_warning":          "Menghentikan pengeluaran sekarang mencegah budget jebol bulan ini.",
        "emergency_fund":          "Dana darurat 3 bulan mengurangi stres finansial dan kebutuhan hutang darurat.",
        "income_diversity":        "Dua sumber pendapatan melipatgandakan ketahanan finansial terhadap krisis.",
        "impulse_spending":        "Mengurangi impulse 30% bisa menambah tabungan 5–10% per bulan.",
        "saving_excellent":        "Mempertahankan ini selama 5 tahun bisa menghasilkan dana investasi yang signifikan.",
        "budget_on_track":         "Konsistensi budget adalah fondasi kemerdekaan finansial.",
        "anomaly_deficit":         "Menutup defisit sekarang mencegah hutang berbunga tinggi bulan depan.",
        "anomaly_income_drop":     "Menyesuaikan pengeluaran dengan pendapatan riil mencegah terkurasnya dana darurat.",
        "anomaly_transfer_heavy":  "Berfokus pada pendapatan riil membuat perencanaan arus kas lebih akurat.",
        "anomaly_concentration":   "Memisahkan pengeluaran besar membuat anggaran bulanan lebih stabil.",
        "anomaly_category_spike":  "Mengendalikan lonjakan kategori menjaga budget tetap terkontrol.",
        "goal_progress":           "Memenuhi goal tepat waktu membangun momentum menabung yang berkelanjutan.",
    }
    for k, v in IMPACTS.items():
        if k in key:
            return v
    return "Perbaikan kecil dan konsisten menghasilkan perubahan finansial besar dalam jangka panjang."


def _grade_label_id(grade: Optional[str]) -> str:
    LABELS = {"A": "sangat baik", "B": "baik", "C": "cukup", "D": "buruk", "F": "kritis"}
    return LABELS.get(grade or "", "tidak diketahui")


def _grade_label_en(grade: Optional[str]) -> str:
    LABELS = {"A": "excellent", "B": "good", "C": "fair", "D": "poor", "F": "critical"}
    return LABELS.get(grade or "", "unknown")


def _pick_motivation(ctx: FinancialContext, results: List[RuleResult]) -> str:
    positives = [r for r in results if r.severity == "positive"]
    highs     = [r for r in results if r.severity == "high"]

    if len(positives) >= 3:
        return "Keuanganmu terus membaik — setiap keputusan kecil hari ini membangun kebebasan finansial masa depanmu."
    elif positives and not highs:
        return "Kamu di jalur yang benar. Konsistensi adalah kunci — tetap pertahankan momentum ini!"
    elif highs:
        return "Masalah keuangan adalah kesempatan untuk belajar. Setiap orang yang berhasil secara finansial pernah berada di posisi ini."
    else:
        return "Langkah terbaik adalah langkah berikutnya. Mulai dari satu perubahan kecil hari ini."


def _pick_motivation_en(ctx: FinancialContext, results: List[RuleResult]) -> str:
    positives = [r for r in results if r.severity == "positive"]
    highs     = [r for r in results if r.severity == "high"]

    if len(positives) >= 3:
        return "Your finances keep improving — every small decision today builds your future financial freedom."
    elif positives and not highs:
        return "You're on the right track. Consistency is the key — keep this momentum going!"
    elif highs:
        return "Financial challenges are learning opportunities. Every financially successful person has been in this position."
    else:
        return "The best step is the next step. Start with one small change today."


# ══════════════════════════════════════════════════════════════════════════════
# § 7  PUBLIC API — Called from api_server.py
# ══════════════════════════════════════════════════════════════════════════════

_composer = InsightComposer()


def rule_based_insights(
    total_income:    float,
    total_expense:   float,
    income_prev:     float,
    expense_prev:    float,
    by_category:     Dict[str, float],
    budget_limits:   Dict[str, float],
    emergency_fund:  float,
    month_label:     str,
    fbs_score:       Optional[float] = None,
    fbs_grade:       Optional[str]   = None,
    impulse_index:   Optional[float] = None,
    income_sources:  int = 1,
    net_worth:       float = 0.0,
    top_transactions: List[Dict] = None,
    profile_name:    str = "",
    profile_type:    str = "",
    transfer_income: float = 0.0,
    anomalies:       List[Dict] = None,
    goals:           List[Dict] = None,
) -> Dict[str, Any]:
    """
    Generate structured financial insights using pure rule-based analysis.
    Returns a dict compatible with the Claude/Ollama insights schema.
    """
    ctx = FinancialContext(
        total_income=total_income,
        total_expense=total_expense,
        income_prev=income_prev,
        expense_prev=expense_prev,
        by_category=by_category or {},
        budget_limits=budget_limits or {},
        emergency_fund=emergency_fund,
        month_label=month_label,
        fbs_score=fbs_score,
        fbs_grade=fbs_grade,
        impulse_index=impulse_index,
        income_sources=income_sources,
        net_worth=net_worth,
        top_transactions=top_transactions or [],
        profile_name=profile_name,
        profile_type=profile_type,
        transfer_income=transfer_income,
        anomalies=anomalies or [],
        goals=goals or [],
    )
    return _composer.compose(ctx)
