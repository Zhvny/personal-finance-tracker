from __future__ import annotations

"""
allocation_engine.py — Smart Saving Allocation Engine
======================================================
Single Responsibility : compute and apply income distribution into buckets.
Open/Closed           : add new buckets by extending saving_rules.json only.
DRY                   : all rule loading, validation, and math in one place.
Clean Architecture    : Domain layer — no FastAPI, no React, no side effects.
                        Caller (api_server.py) handles DB writes.

Buckets
-------
  expenses        — informational only (not written to DB, shown in UI)
  bank_savings    — written to cash_split.bank_savings (+ delta)
  emergency_fund  — written to manual_balances WHERE key='emergency_fund'
  investment      — informational only

Flow
----
  income added (amount = X)
    → AllocationEngine.compute(X, rules) → AllocationResult
    → api_server writes AllocationResult.db_writes to DB
    → response includes allocation breakdown
"""
import logging

logger = logging.getLogger(__name__)


import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# ── Config path ───────────────────────────────────────────────────────────────
_RULES_PATH = Path(__file__).parent / "saving_rules.json"

# ── Buckets that trigger DB writes ───────────────────────────────────────────
DB_WRITE_BUCKETS = {"bank_savings", "emergency_fund"}


# ══════════════════════════════════════════════════════════════════════════════
# § DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BucketResult:
    bucket:      str
    label:       str
    description: str
    pct:         float   # 0–100
    amount:      float   # IDR


@dataclass
class AllocationResult:
    income_amount: float
    buckets:       List[BucketResult]
    enabled:       bool
    mode:          str
    # DB write map: bucket → amount delta (only for DB_WRITE_BUCKETS)
    db_writes:     Dict[str, float] = field(default_factory=dict)
    # Validation warnings (non-fatal)
    warnings:      List[str]       = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "income_amount": self.income_amount,
            "enabled":       self.enabled,
            "mode":          self.mode,
            "buckets": [
                {
                    "bucket":      b.bucket,
                    "label":       b.label,
                    "description": b.description,
                    "pct":         b.pct,
                    "amount":      round(b.amount),
                }
                for b in self.buckets
            ],
            "db_writes": {k: round(v) for k, v in self.db_writes.items()},
            "warnings":  self.warnings,
        }


# ══════════════════════════════════════════════════════════════════════════════
# § RULES LOADER
# ══════════════════════════════════════════════════════════════════════════════

def load_rules() -> dict:
    """
    Load saving_rules.json. Returns default rules if file missing/corrupt.
    Never raises.
    """
    try:
        with open(_RULES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return _default_rules()


def save_rules(rules: dict) -> bool:
    """
    Persist updated rules to saving_rules.json.
    Returns True on success.
    """
    try:
        _RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_RULES_PATH, "w", encoding="utf-8") as f:
            json.dump(rules, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        logger.exception("Error while computing allocation")
        return False


def validate_rules(rules: dict) -> List[str]:
    """
    Validate rule structure. Returns list of error strings (empty = valid).
    """
    errors = []
    rule_list = rules.get("rules", [])
    if not rule_list:
        errors.append("rules list is empty")
        return errors

    total_pct = sum(r.get("pct", 0) for r in rule_list)
    if abs(total_pct - 100) > 0.01:
        errors.append(f"Total pct must equal 100, got {total_pct}")

    for r in rule_list:
        if "bucket" not in r:
            errors.append(f"Rule missing 'bucket': {r}")
        if not (0 <= r.get("pct", -1) <= 100):
            errors.append(f"Invalid pct for bucket '{r.get('bucket')}': {r.get('pct')}")

    return errors


def _default_rules() -> dict:
    return {
        "enabled": True,
        "mode": "percentage",
        "rules": [
            {"bucket": "expenses",       "pct": 50, "label": "Biaya Hidup",   "description": ""},
            {"bucket": "bank_savings",   "pct": 30, "label": "Tabungan Bank", "description": ""},
            {"bucket": "investment",     "pct": 10, "label": "Investasi",     "description": ""},
            {"bucket": "emergency_fund", "pct": 10, "label": "Dana Darurat",  "description": ""},
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# § ALLOCATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class AllocationEngine:
    """
    Pure computation engine. Stateless — each call is independent.
    No DB access. Returns AllocationResult that caller persists.
    """

    @staticmethod
    def compute(income_amount: float, rules: Optional[dict] = None) -> AllocationResult:
        """
        Split income_amount across buckets per rules.
        If rules is None, loads from saving_rules.json.

        Returns AllocationResult.
        If allocation is disabled, returns AllocationResult with all amounts=0.
        """
        if rules is None:
            rules = load_rules()

        enabled = bool(rules.get("enabled", True))
        mode    = rules.get("mode", "percentage")
        warnings: List[str] = []

        if not enabled or income_amount <= 0:
            return AllocationResult(
                income_amount=income_amount,
                buckets=[],
                enabled=enabled,
                mode=mode,
                db_writes={},
                warnings=["Allocation disabled or income is zero."] if income_amount <= 0 else [],
            )

        rule_list = rules.get("rules", [])
        errs = validate_rules(rules)
        if errs:
            warnings.extend(errs)

        buckets: List[BucketResult] = []
        db_writes: Dict[str, float] = {}
        remainder = income_amount

        for i, r in enumerate(rule_list):
            bucket = r.get("bucket", "unknown")
            pct    = float(r.get("pct", 0))
            label  = r.get("label", bucket)
            desc   = r.get("description", "")

            if i == len(rule_list) - 1:
                # Last bucket absorbs rounding remainder
                amount = remainder
            else:
                amount = round(income_amount * pct / 100, 2)
                remainder -= amount

            buckets.append(BucketResult(
                bucket=bucket, label=label, description=desc,
                pct=pct, amount=amount,
            ))

            if bucket in DB_WRITE_BUCKETS:
                db_writes[bucket] = amount

        return AllocationResult(
            income_amount=income_amount,
            buckets=buckets,
            enabled=enabled,
            mode=mode,
            db_writes=db_writes,
            warnings=warnings,
        )

    @staticmethod
    def simulate(income_amount: float, rules: Optional[dict] = None) -> dict:
        """
        Preview allocation without any DB write. Returns dict for API response.
        """
        result = AllocationEngine.compute(income_amount, rules)
        return result.to_dict()
