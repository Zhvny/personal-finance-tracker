"""
behavioral-finance/domain/models.py
=====================================
Domain Layer — Pure business entities and scoring models.

Clean Architecture: innermost ring. No I/O, no frameworks, no side effects.
SOLID  : Single Responsibility per class; Open/Closed via score strategies.
DRY    : all constants defined once; formulas live here, nowhere else.
YAGNI  : only models actually used by the application layer are defined.

Behavioral Finance theories encoded here (internal only — not rendered in UI):
  • Prospect Theory      (Kahneman & Tversky 1979)
  • Loss Aversion        (losses weighted ~2× vs gains)
  • Present Bias         (Laibson 1997 — weekend/night purchases weighted higher)
  • Mental Accounting    (Thaler 1999 — discretionary categories weighted higher)
  • Risk Diversification (single-source income penalised)
  • Financial Fragility  (Housel 2020 — emergency buffer weight)
"""

from dataclasses import dataclass
from typing import Dict, List

# ══════════════════════════════════════════════════════════════════════════════
# § 1  CONSTANTS — Single source of truth
# ══════════════════════════════════════════════════════════════════════════════

# Financial Behaviour Score weights (must sum to 1.0)
FBS_WEIGHTS = {
    "saving_rate":       0.30,
    "budget_adherence":  0.25,
    "impulse_control":   0.20,
    "consistency":       0.15,
    "emergency_buffer":  0.10,
}

# Category risk multipliers (Mental Accounting theory)
CATEGORY_RISK = {
    "entertainment": 1.4,
    "shopping":      1.3,
    "food":          1.0,
    "transport":     0.9,
    "housing":       0.7,
    "health":        0.6,
    "education":     0.5,
    "investment":    0.3,
    "other":         1.0,
}

# Loss aversion asymmetry factor (Prospect Theory: losses feel ~2× larger)
LOSS_AVERSION_FACTOR = 1.8

# Present Bias: weekend/evening transactions scored higher impulsivity
WEEKEND_BIAS   = 1.2
EVENING_BIAS   = 1.15   # 18:00–23:59

# FBS grade thresholds
FBS_GRADES = [
    (85, "A", "Excellent",  "#34d399"),
    (70, "B", "Good",       "#60a5fa"),
    (55, "C", "Fair",       "#fbbf24"),
    (40, "D", "Poor",       "#f87171"),
    ( 0, "F", "Critical",   "#ef4444"),
]


# ══════════════════════════════════════════════════════════════════════════════
# § 2  VALUE OBJECTS — Immutable, validated domain data
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Transaction:
    """Immutable domain entity representing a single financial transaction."""
    date:     str        # ISO date string YYYY-MM-DD
    amount:   float
    category: str
    is_income: bool = False

    def is_weekend(self) -> bool:
        from datetime import date, datetime
        try:
            if isinstance(self.date, (datetime, date)):
                return self.date.weekday() >= 5
            return datetime.fromisoformat(str(self.date)).weekday() >= 5
        except (ValueError, TypeError):
            return False


@dataclass(frozen=True)
class FBSResult:
    """Result of Financial Behaviour Score computation."""
    score:        float                  # 0–100
    grade:        str                    # A / B / C / D / F
    label:        str                    # "Excellent" etc.
    color:        str                    # hex color for UI
    component_scores: Dict[str, float]   # per-weight breakdown
    saving_rate:  float
    impulse_index: float


@dataclass(frozen=True)
class FragilityResult:
    """Result of Financial Fragility Score computation."""
    score:             float   # 0–100, higher = more stable
    grade:             str
    label:             str
    color:             str
    income_sources:    int
    emergency_months:  float   # how many months of expenses covered
    asset_concentration: float # 0–1, higher = more concentrated (riskier)


@dataclass(frozen=True)
class ImpulseTransaction:
    """Enriched transaction with impulsivity scoring."""
    transaction: Transaction
    impulse_score: float       # 0–1
    risk_category: str
    bias_applied: str          # "weekend" / "evening" / "none"


# ══════════════════════════════════════════════════════════════════════════════
# § 3  DOMAIN SERVICES — Pure scoring functions
# ══════════════════════════════════════════════════════════════════════════════

def fbs_grade(score: float) -> tuple:
    """Return (grade, label, color) for an FBS score."""
    for threshold, grade, label, color in FBS_GRADES:
        if score >= threshold:
            return grade, label, color
    return "F", "Critical", "#ef4444"


def compute_impulse_score(tx: Transaction) -> float:
    """
    Compute impulsivity score for a single transaction (0–1).
    Applies Present Bias + Mental Accounting theories internally.
    """
    base  = CATEGORY_RISK.get(tx.category, 1.0) / max(CATEGORY_RISK.values())
    bias  = WEEKEND_BIAS if tx.is_weekend() else 1.0
    score = min(1.0, base * bias)
    return round(score, 4)


def compute_fbs(
    transactions: List[Transaction],
    income_this: float,
    income_prev: float,
    expense_this: float,
    expense_prev: float,
    emergency_fund: float = 0.0,
) -> FBSResult:
    """
    Compute Financial Behaviour Score (0–100).
    All theory application stays here — not exposed to UI layer.
    """
    # Saving Rate component
    saving_rate = max(0.0, (income_this - expense_this) / income_this) if income_this > 0 else 0.0
    saving_score = min(1.0, saving_rate / 0.30)  # 30% saving rate = perfect score

    # Budget Adherence (vs previous month baseline)
    if expense_prev > 0:
        ratio = expense_this / expense_prev
        # Loss Aversion: overspending penalised asymmetrically
        if ratio <= 1.0:
            budget_score = 1.0
        else:
            penalty = (ratio - 1.0) * LOSS_AVERSION_FACTOR
            budget_score = max(0.0, 1.0 - penalty)
    else:
        budget_score = 0.5  # neutral — no baseline

    # Impulse Control (avg impulse score across expense transactions)
    expense_txs = [t for t in transactions if not t.is_income]
    if expense_txs:
        avg_impulse = sum(compute_impulse_score(t) for t in expense_txs) / len(expense_txs)
        impulse_score = 1.0 - avg_impulse
    else:
        avg_impulse = 0.0
        impulse_score = 1.0

    # Consistency (income stability)
    if income_prev > 0:
        consistency = min(1.0, income_this / income_prev)
    else:
        consistency = 0.5

    # Emergency Buffer (3 months expenses = perfect)
    monthly_expense = expense_this or expense_prev or 1
    buffer_months = emergency_fund / monthly_expense if monthly_expense > 0 else 0
    buffer_score = min(1.0, buffer_months / 3.0)

    components = {
        "saving_rate":      saving_score,
        "budget_adherence": budget_score,
        "impulse_control":  impulse_score,
        "consistency":      consistency,
        "emergency_buffer": buffer_score,
    }

    raw_score = sum(v * FBS_WEIGHTS[k] for k, v in components.items()) * 100
    score = round(min(100.0, max(0.0, raw_score)), 1)
    grade, label, color = fbs_grade(score)

    return FBSResult(
        score=score, grade=grade, label=label, color=color,
        component_scores={k: round(v * 100, 1) for k, v in components.items()},
        saving_rate=round(saving_rate * 100, 1),
        impulse_index=round(avg_impulse * 100, 1),
    )


def compute_fragility(
    income_sources: int,
    expense_this: float,
    emergency_fund: float,
    asset_values: Dict[str, float],
) -> FragilityResult:
    """
    Compute Financial Fragility Score (0–100, higher = more stable).
    Applies Risk Diversification + Financial Fragility theories.
    """
    # Income diversification (more sources = safer)
    income_score = min(1.0, income_sources / 3.0)

    # Emergency buffer (3 months = full score)
    monthly = expense_this or 1
    months_covered = emergency_fund / monthly
    buffer_score = min(1.0, months_covered / 3.0)

    # Asset concentration (lower = more diversified = safer)
    total_assets = sum(asset_values.values()) or 1
    if asset_values:
        max_share = max(asset_values.values()) / total_assets
        # Herfindahl index proxy: lower = more diverse
        concentration = sum((v / total_assets) ** 2 for v in asset_values.values())
        concentration_score = 1.0 - concentration
    else:
        max_share = 0.0
        concentration = 0.0
        concentration_score = 0.5

    raw = (income_score * 0.35 + buffer_score * 0.40 + concentration_score * 0.25) * 100
    score = round(min(100.0, max(0.0, raw)), 1)
    grade, label, color = fbs_grade(score)

    return FragilityResult(
        score=score, grade=grade, label=label, color=color,
        income_sources=income_sources,
        emergency_months=round(months_covered, 1),
        asset_concentration=round(concentration, 3),
    )
