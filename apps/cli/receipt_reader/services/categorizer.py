"""
services/categorizer.py — Categorizer Service with Persistent Merchant Memory
===============================================================================
Priority lookup chain (highest confidence wins):
  1. merchant_map.db  (persistent memory, cross-session, shared with GUI)
  2. in-session cache  (fast repeated lookup within same run)
  3. SmartCategorizer  (keyword + pattern + amount heuristics)

Single Responsibility : orchestrate categorization, delegate to specialists.
DRY                   : correction path writes to BOTH cache and DB atomically.
Open/Closed           : new lookup strategies slot in without changing callers.
"""

from __future__ import annotations

from collections import Counter
from typing import List, Optional

from apps.cli.receipt_reader.core.categorizer import ClassificationResult
from apps.cli.receipt_reader.core.categorizer import UniversalCategorizer as SmartCategorizer
from apps.cli.receipt_reader.core.interfaces import ExpenseCategory, IncomeCategory, ReceiptData
from apps.cli.receipt_reader.core.merchant_memory_bridge import MerchantMemoryBridge

# ══════════════════════════════════════════════════════════════════════════════
# § HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _str_to_enum(value: str):
    """Convert category string → Enum. Returns None if not found."""
    for cat in (*ExpenseCategory, *IncomeCategory):
        if cat.value == value:
            return cat
    return None


# ══════════════════════════════════════════════════════════════════════════════
# § SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class CategorizerService:
    """
    Categorization service with three-layer lookup:
      DB memory → session cache → smart keyword engine.

    DB memory is the shared merchant_map.db used by the GUI.
    Any user correction (CLI or GUI) is reflected immediately for both layers.
    """

    def __init__(self):
        self._categorizer  = SmartCategorizer()
        self._bridge       = MerchantMemoryBridge()
        self._cache: dict  = {}          # in-session: normalized_key → Enum | str
        self._corrections: List[dict] = []

    # ── Primary API ────────────────────────────────────────────────────────────

    def categorize(self, receipt: ReceiptData) -> ClassificationResult:
        """
        Categorize receipt using three-layer priority chain.
        Returns ClassificationResult with method indicating which layer matched.
        """
        merchant = receipt.merchant_name or ""
        cache_key = merchant.lower().strip()

        # ── Layer 1: persistent DB memory ──────────────────────────────────────
        db_category_str = self._bridge.lookup(merchant)
        if db_category_str:
            category = _str_to_enum(db_category_str) or db_category_str
            # Warm session cache to avoid repeat DB round-trip
            self._cache[cache_key] = category
            return ClassificationResult(
                category=category,
                confidence=0.98,    # Highest confidence — user-confirmed memory
                method="merchant_memory",
                matched_keywords=[merchant],
                reasoning=f"Merchant memory match: {merchant!r} → {db_category_str}",
            )

        # ── Layer 2: in-session cache ───────────────────────────────────────────
        if cache_key in self._cache:
            return ClassificationResult(
                category=self._cache[cache_key],
                confidence=0.95,
                method="session_cache",
                matched_keywords=[],
                reasoning=f"Session cache hit for '{merchant}'",
            )

        # ── Layer 3: keyword/pattern engine ────────────────────────────────────
        result = self._categorizer.classify(receipt)
        if result.confidence > 0.8:
            self._cache[cache_key] = result.category
        return result

    def categorize_item(self, item_name: str) -> Optional[ExpenseCategory]:
        """Categorize individual line item (bypasses merchant memory)."""
        return self._categorizer.classify_item(item_name)

    # ── Correction API ─────────────────────────────────────────────────────────

    def record_correction(self, receipt: ReceiptData, correct_category: str) -> None:
        """
        Record user correction.
        Writes to both session cache AND persistent merchant_map.db so future
        scans (CLI or GUI) immediately benefit.
        """
        merchant  = receipt.merchant_name or ""
        cache_key = merchant.lower().strip()

        # Persist to DB (shared with GUI)
        self._bridge.remember(merchant, correct_category)

        # Update session cache
        enum_val = _str_to_enum(correct_category)
        self._cache[cache_key] = enum_val if enum_val is not None else correct_category

        # Record for stats / export
        self._corrections.append({
            "merchant":          merchant,
            "original_category": str(getattr(receipt, "category", "")),
            "correct_category":  correct_category,
            "raw_text":          (receipt.raw_ocr_text or "")[:100],
        })

    # ── Stats / Export ─────────────────────────────────────────────────────────

    def get_correction_stats(self) -> dict:
        """Return session correction statistics."""
        if not self._corrections:
            return {"total_corrections": 0}
        original_cats = Counter(c["original_category"] for c in self._corrections)
        return {
            "total_corrections":          len(self._corrections),
            "most_corrected_categories":  dict(original_cats.most_common(5)),
            "merchant_memory_available":  self._bridge.is_available(),
        }

    def export_corrections(self, filepath: str = "corrections.json") -> None:
        """Export corrections for audit/ML training."""
        import json
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self._corrections, f, indent=2, ensure_ascii=False)
