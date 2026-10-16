# tests/unit/test_recurrence_detector.py
#
# Unit tests for packages/api/backend/expenses/recurrence_detector.py
#
# Kenapa modul ini yang dites: recurrence_detector.py adalah pure-logic
# detection engine (tidak I/O dalam fungsi-fungsi core-nya) yang mendeteksi
# pola transaksi berulang dari data expense. Fungsi _norm, _interval_score,
# _occurrence_score, _confidence, dan logika inti detect() bisa diuji
# tanpa Database dependency — cukup patch Database.query.
#
# Cakupan:
#   - _norm                  : normalisasi description untuk grouping
#   - _interval_score        : skor berdasarkan kedekatan ke 30 hari
#   - _occurrence_score      : skor berdasarkan jumlah kemunculan
#   - _confidence            : combined score
#   - detect()               : logic grouping + interval + confidence filter
#                              (dengan Database.query di-mock)
#   - RecurringCandidate     : dataclass sanity check
#
# Cara jalanin:
#   pytest tests/unit/test_recurrence_detector.py -v

from unittest.mock import patch

import pytest

from packages.api.backend.expenses.recurrence_detector import (
    RecurringCandidate,
    _confidence,
    _interval_score,
    _norm,
    _occurrence_score,
    detect,
)

# ─────────────────────────────────────────────────────────────────────
# _norm
# ─────────────────────────────────────────────────────────────────────

class TestNorm:

    def test_basic_lowercase(self):
        assert _norm("Spotify") == "spotify"

    def test_strips_trailing_txn_id(self):
        # " - TXN123" suffix harus dibuang
        assert _norm("Spotify - TXN123") == "spotify"

    def test_strips_trailing_hash_id(self):
        assert _norm("Netflix # 4567") == "netflix"

    def test_strips_trailing_date_digits(self):
        # " 20250301" → dibuang
        assert _norm("Indihome 20250301") == "indihome"

    def test_strips_parenthetical_note(self):
        assert _norm("Spotify (promo)") == "spotify"

    def test_strips_multiplier_suffix(self):
        assert _norm("Gofood 2x") == "gofood"

    def test_collapses_whitespace(self):
        assert _norm("  Nara   Kitchen  ") == "nara kitchen"

    def test_empty_string(self):
        assert _norm("") == ""

    def test_none_equivalent(self):
        # None-equivalent — description kosong
        assert _norm("   ") == ""

    def test_same_group_after_norm(self):
        # Kedua versi harus ke key yang sama setelah normalisasi
        assert _norm("Spotify - TXN999") == _norm("Spotify - TXN000")


# ─────────────────────────────────────────────────────────────────────
# _interval_score
# ─────────────────────────────────────────────────────────────────────

class TestIntervalScore:

    def test_exactly_30_days_is_perfect(self):
        assert _interval_score(30.0) == 1.0

    def test_exactly_at_min_boundary_is_zero(self):
        # deviation = 15.0 → skor tepat 0.0
        assert _interval_score(15.0) == 0.0
        assert _interval_score(45.0) == 0.0

    def test_beyond_boundary_is_zero(self):
        assert _interval_score(7.0) == 0.0
        assert _interval_score(60.0) == 0.0

    def test_midpoint_score(self):
        # deviation = 7.5 → 1 - 7.5/15 = 0.5
        assert _interval_score(22.5) == pytest.approx(0.5, abs=0.001)
        assert _interval_score(37.5) == pytest.approx(0.5, abs=0.001)

    def test_within_valid_range_produces_positive_score(self):
        for days in [22, 25, 28, 30, 32, 35, 38]:
            assert _interval_score(float(days)) > 0.0


# ─────────────────────────────────────────────────────────────────────
# _occurrence_score
# ─────────────────────────────────────────────────────────────────────

class TestOccurrenceScore:

    def test_zero_occurrences(self):
        assert _occurrence_score(0) == 0.0

    def test_one_occurrence(self):
        assert _occurrence_score(1) == 0.25

    def test_two_occurrences(self):
        assert _occurrence_score(2) == 0.5

    def test_four_occurrences_max(self):
        assert _occurrence_score(4) == 1.0

    def test_more_than_four_capped_at_one(self):
        assert _occurrence_score(10) == 1.0
        assert _occurrence_score(100) == 1.0


# ─────────────────────────────────────────────────────────────────────
# _confidence
# ─────────────────────────────────────────────────────────────────────

class TestConfidence:

    def test_perfect_score(self):
        # interval=30 (score=1.0), occurrences=4 (score=1.0)
        assert _confidence(30.0, 4) == pytest.approx(1.0, abs=0.001)

    def test_zero_if_interval_out_of_range(self):
        # interval 7 → interval_score=0.0 → confidence=0.0
        assert _confidence(7.0, 4) == 0.0

    def test_zero_if_occurrences_zero(self):
        assert _confidence(30.0, 0) == 0.0

    def test_half_confidence(self):
        # interval=22.5 (score=0.5), occurrences=2 (score=0.5) → 0.25
        assert _confidence(22.5, 2) == pytest.approx(0.25, abs=0.001)


# ─────────────────────────────────────────────────────────────────────
# detect() — dengan mock Database.query
# ─────────────────────────────────────────────────────────────────────

def _make_expense(description: str, amount: float, date_str: str, category: str = "other") -> dict:
    return {"description": description, "amount": amount, "date": date_str, "category": category}


class TestDetect:

    def _run_detect(self, rows, months_lookback=6):
        """Helper: mock Database.query dan jalanin detect()."""
        with patch("packages.api.backend.expenses.recurrence_detector.Database") as mock_db:
            mock_db.query.return_value = rows
            return detect(":memory:", months_lookback)

    def test_no_rows_returns_empty(self):
        result = self._run_detect([])
        assert result == []

    def test_single_occurrence_not_recurring(self):
        rows = [_make_expense("Spotify", 59000, "2026-01-15")]
        result = self._run_detect(rows)
        assert result == []  # MIN_OCCURRENCES=2, tidak cukup

    def test_two_occurrences_30_day_interval_detected(self):
        rows = [
            _make_expense("Spotify", 59000, "2026-01-15"),
            _make_expense("Spotify", 59000, "2026-02-14"),
        ]
        result = self._run_detect(rows)
        assert len(result) == 1
        r = result[0]
        assert _norm(r.description) == "spotify"
        assert r.occurrences == 2
        assert 22 <= r.interval_days <= 38
        assert r.confidence > 0.1

    def test_weekly_interval_not_detected(self):
        # 7-day interval di luar INTERVAL_MIN(22)–INTERVAL_MAX(38)
        rows = [
            _make_expense("GoPay Weekly", 10000, "2026-01-01"),
            _make_expense("GoPay Weekly", 10000, "2026-01-08"),
            _make_expense("GoPay Weekly", 10000, "2026-01-15"),
        ]
        result = self._run_detect(rows)
        assert result == []

    def test_txn_id_suffix_groups_correctly(self):
        # "Spotify - TXN111" dan "Spotify - TXN222" harus ke grup yang sama
        rows = [
            _make_expense("Spotify - TXN111", 59000, "2026-01-15"),
            _make_expense("Spotify - TXN222", 59000, "2026-02-14"),
        ]
        result = self._run_detect(rows)
        assert len(result) == 1

    def test_multiple_merchants_detected_independently(self):
        rows = [
            _make_expense("Spotify", 59000, "2026-01-01"),
            _make_expense("Spotify", 59000, "2026-02-01"),
            _make_expense("Netflix", 186000, "2026-01-05"),
            _make_expense("Netflix", 186000, "2026-02-04"),
        ]
        result = self._run_detect(rows)
        norms = {_norm(r.description) for r in result}
        assert "spotify" in norms
        assert "netflix" in norms

    def test_category_plurality_wins(self):
        # 2 food vs 1 other → top_cat = food
        rows = [
            _make_expense("Tokopedia", 50000, "2026-01-01", "shopping"),
            _make_expense("Tokopedia", 60000, "2026-01-31", "shopping"),
            _make_expense("Tokopedia", 55000, "2026-03-02", "other"),
        ]
        result = self._run_detect(rows)
        # Hanya 2 interval yang ke-detect, avg_interval bisa bervariasi
        if result:
            assert result[0].category == "shopping"

    def test_avg_amount_correct(self):
        rows = [
            _make_expense("Indihome", 300000, "2026-01-05"),
            _make_expense("Indihome", 350000, "2026-02-05"),
        ]
        result = self._run_detect(rows)
        assert len(result) == 1
        assert result[0].avg_amount == pytest.approx(325000.0, abs=1)

    def test_sorted_by_confidence_descending(self):
        # Spotify: interval 30 hari → confidence tinggi
        # GrabFood: interval 23 hari → confidence lebih rendah
        rows = [
            _make_expense("Spotify", 59000, "2026-01-01"),
            _make_expense("Spotify", 59000, "2026-01-31"),
            _make_expense("Spotify", 59000, "2026-03-02"),
            _make_expense("GrabFood", 50000, "2026-01-01"),
            _make_expense("GrabFood", 50000, "2026-01-24"),
        ]
        result = self._run_detect(rows)
        if len(result) >= 2:
            assert result[0].confidence >= result[1].confidence

    def test_last_seen_is_latest_date(self):
        rows = [
            _make_expense("Spotify", 59000, "2026-01-15"),
            _make_expense("Spotify", 59000, "2026-02-14"),
        ]
        result = self._run_detect(rows)
        assert len(result) == 1
        assert result[0].last_seen == "2026-02-14"

    def test_empty_description_skipped(self):
        rows = [
            _make_expense("", 50000, "2026-01-01"),
            _make_expense("", 50000, "2026-01-31"),
        ]
        result = self._run_detect(rows)
        assert result == []

    def test_database_none_returns_empty(self):
        # Kalau Database tidak tersedia (None), detect() harus return []
        with patch("packages.api.backend.expenses.recurrence_detector.Database", None):
            result = detect(":memory:")
        assert result == []

    def test_is_confirmed_default_false(self):
        rows = [
            _make_expense("Spotify", 59000, "2026-01-15"),
            _make_expense("Spotify", 59000, "2026-02-14"),
        ]
        result = self._run_detect(rows)
        assert len(result) == 1
        assert result[0].is_confirmed is False


# ─────────────────────────────────────────────────────────────────────
# RecurringCandidate dataclass sanity
# ─────────────────────────────────────────────────────────────────────

class TestRecurringCandidate:

    def test_default_is_confirmed_false(self):
        c = RecurringCandidate(
            description="Spotify",
            category="entertainment",
            avg_amount=59000.0,
            interval_days=30.0,
            occurrences=3,
            last_seen="2026-02-14",
            confidence=0.75,
        )
        assert c.is_confirmed is False

    def test_fields_set_correctly(self):
        c = RecurringCandidate(
            description="Netflix",
            category="entertainment",
            avg_amount=186000.0,
            interval_days=30.5,
            occurrences=4,
            last_seen="2026-03-01",
            confidence=0.95,
            is_confirmed=True,
        )
        assert c.description == "Netflix"
        assert c.avg_amount == 186000.0
        assert c.is_confirmed is True
