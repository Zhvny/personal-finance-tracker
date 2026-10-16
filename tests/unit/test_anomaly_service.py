"""
Phase 12 — Deterministic anomaly detection tests.

Covers packages/api/backend/finance/anomaly_service.py:

  * window/baseline bounds validation
  * category_spike rule (ratio, min_delta, count>=2, income too)
  * oversized_tx rule (baseline-relative, min_large guard)
  * no-anomaly / empty-ledger cases
  * persistence: idempotent check (dedup per year/month/rule/category), list
  * Telegram renderer (format_anomalies_text)

Hermetic SQLite fixture — safe name without a canonical bridge target.
"""
from datetime import date, timedelta

import pytest

from packages.api.backend.finance import anomaly_service as an
from packages.api.backend.finance import ledger_engine as ledger


@pytest.fixture
def ledger_db(tmp_path):
    path = str(tmp_path / "anomaly_ledger.sqlite")
    ledger.seed_defaults(path)
    return path


def _tx(ledger_db, ttype, amount, tx_date, category, description=None):
    return ledger.record_transaction(
        ledger_db, ttype=ttype, amount=amount, tx_date=tx_date,
        category=category, description=description, source="test",
    )


def _seed_calendar(ledger_db, as_of=date(2026, 8, 17)):
    """Steady baseline: 500k/day Food for baseline_days (90) before the window."""
    baseline_start = as_of - timedelta(days=90 + 30)
    d = baseline_start
    while d < as_of - timedelta(days=30):
        _tx(ledger_db, "expense", 500_000, d, "Food", description="Belanja rutin")
        d += timedelta(days=1)


# ═════════════════════════════════════════════════════════════════════════════
# § Validation
# ═════════════════════════════════════════════════════════════════════════════

def test_params_validation(ledger_db):
    with pytest.raises(an.AnomalyError):
        an.detect_anomalies(ledger_db, window_days=3)
    with pytest.raises(an.AnomalyError):
        an.detect_anomalies(ledger_db, window_days=200)
    with pytest.raises(an.AnomalyError):
        an.detect_anomalies(ledger_db, baseline_days=3)
    with pytest.raises(an.AnomalyError):
        an.detect_anomalies(ledger_db, spike_ratio=1.0)
    with pytest.raises(an.AnomalyError):
        an.detect_anomalies(ledger_db, oversized_factor=1.0)


def test_empty_ledger_no_anomalies(ledger_db):
    result = an.detect_anomalies(ledger_db)
    assert result["anomalies"] == []
    assert result["window"]["start"] <= result["window"]["end"]


# ═════════════════════════════════════════════════════════════════════════════
# § Category spike rule
# ═════════════════════════════════════════════════════════════════════════════

def test_category_spike_detected(ledger_db):
    as_of = date(2026, 8, 17)
    _seed_calendar(ledger_db, as_of)
    # spike: 1.5jt/day Food for the 30-day window (3x baseline 500k/day)
    for i in range(30):
        _tx(ledger_db, "expense", 1_500_000, as_of - timedelta(days=i), "Food", description="Spike")
    result = an.detect_anomalies(ledger_db, as_of=as_of)
    spikes = [a for a in result["anomalies"] if a["rule"] == "category_spike"]
    assert len(spikes) == 1
    s = spikes[0]
    assert s["category"] == "Food"
    assert s["ratio"] == pytest.approx(3.0, abs=0.1)
    assert s["severity"] == "high"
    assert s["delta"] > 0


def test_spike_below_ratio_not_detected(ledger_db):
    as_of = date(2026, 8, 17)
    _seed_calendar(ledger_db, as_of)
    # 1.5x baseline but ratio threshold 2.0 → no anomaly
    for i in range(30):
        _tx(ledger_db, "expense", 750_000, as_of - timedelta(days=i), "Food", description="Naik")
    result = an.detect_anomalies(ledger_db, as_of=as_of)
    assert result["anomalies"] == []


def test_spike_below_min_delta_not_detected(ledger_db):
    as_of = date(2026, 8, 17)
    _seed_calendar(ledger_db, as_of)
    # tiny category: baseline 10k/day (3tx in baseline), spike 30k/day → ratio 3x
    # but delta = 30*30k - 10k*30 = 600k >= min_delta 100k → detected
    for i in range(3):
        _tx(ledger_db, "expense", 10_000, as_of - timedelta(days=40 + i), "Snack", description="Baseline")
    for i in range(30):
        _tx(ledger_db, "expense", 30_000, as_of - timedelta(days=i), "Snack", description="Spike")
    result = an.detect_anomalies(ledger_db, as_of=as_of)
    assert any(a["category"] == "Snack" for a in result["anomalies"])

    # raise min_delta above the delta → no longer detected
    result2 = an.detect_anomalies(ledger_db, min_delta=1_000_000.0, as_of=as_of)
    assert not any(a["category"] == "Snack" for a in result2["anomalies"])


def test_single_tx_category_never_spikes(ledger_db):
    """count < 2 in the window → rule 1 skipped even if ratio huge."""
    as_of = date(2026, 8, 17)
    _seed_calendar(ledger_db, as_of)
    _tx(ledger_db, "expense", 10_000_000, as_of, "Bike", description="Gede")
    result = an.detect_anomalies(ledger_db, as_of=as_of)
    assert not any(a["rule"] == "category_spike" and a["category"] == "Bike" for a in result["anomalies"])


def test_income_spike_detected(ledger_db):
    as_of = date(2026, 8, 17)
    for i in range(3):
        _tx(ledger_db, "income", 5_000_000, as_of - timedelta(days=60 + i * 30), "Salary", description="Gaji")
    _tx(ledger_db, "income", 50_000_000, as_of, "Salary", description="Bonus besar")
    _tx(ledger_db, "income", 50_000_000, as_of - timedelta(days=5), "Salary", description="Bonus besar 2")
    result = an.detect_anomalies(ledger_db, as_of=as_of)
    assert any(a["rule"] == "category_spike" and a["ttype"] == "income" for a in result["anomalies"])


# ═════════════════════════════════════════════════════════════════════════════
# § Oversized transaction rule
# ═════════════════════════════════════════════════════════════════════════════

def test_oversized_tx_detected(ledger_db):
    as_of = date(2026, 8, 17)
    _seed_calendar(ledger_db, as_of)  # Food baseline 500k/day
    _tx(ledger_db, "expense", 12_000_000, as_of, "Food", description="Hajatan")  # 24x baseline
    result = an.detect_anomalies(ledger_db, as_of=as_of)
    big = [a for a in result["anomalies"] if a["rule"] == "oversized_tx"]
    assert len(big) == 1
    assert big[0]["category"] == "Food"
    assert big[0]["ratio"] == pytest.approx(24.0, abs=0.5)
    assert big[0]["severity"] == "high"
    assert "Hajatan" in big[0]["evidence"]


def test_oversized_below_min_large_not_detected(ledger_db):
    as_of = date(2026, 8, 17)
    _seed_calendar(ledger_db, as_of)
    _tx(ledger_db, "expense", 8_000_000, as_of, "Food", description="Sedang")  # 16x but < 3x min_large
    result = an.detect_anomalies(ledger_db, min_large=5_000_000.0, as_of=as_of)
    # min_large 5jt: 8jt >= 5jt → detected; with default 500k also detected.
    assert any(a["rule"] == "oversized_tx" for a in result["anomalies"])
    result2 = an.detect_anomalies(ledger_db, min_large=9_000_000.0, as_of=as_of)
    assert not any(a["rule"] == "oversized_tx" for a in result2["anomalies"])


# ═════════════════════════════════════════════════════════════════════════════
# § Persistence (idempotent n8n entry point)
# ═════════════════════════════════════════════════════════════════════════════

def test_check_persists_once_and_lists(ledger_db):
    as_of = date(2026, 8, 17)
    _seed_calendar(ledger_db, as_of)
    for i in range(30):
        _tx(ledger_db, "expense", 1_500_000, as_of - timedelta(days=i), "Food", description="Spike")

    first = an.check_anomaly_alerts(ledger_db, as_of=as_of)
    assert first["detected"] >= 1
    assert len(first["new_alerts"]) >= 1

    second = an.check_anomaly_alerts(ledger_db, as_of=as_of)
    assert second["new_alerts"] == []  # dedup

    alerts = an.list_anomaly_alerts(ledger_db)
    assert len(alerts) == len(first["new_alerts"])
    assert alerts[0]["rule"] == "category_spike"
    assert alerts[0]["category"] == "Food"
    assert alerts[0]["severity"] == "high"

    filtered = an.list_anomaly_alerts(ledger_db, year=2026, month=8)
    assert len(filtered) == len(alerts)
    assert an.list_anomaly_alerts(ledger_db, year=2020, month=1) == []


def test_list_creates_table_when_absent(tmp_path):
    path = str(tmp_path / "anomaly_empty.sqlite")
    assert an.list_anomaly_alerts(path) == []


# ═════════════════════════════════════════════════════════════════════════════
# § Telegram renderer
# ═════════════════════════════════════════════════════════════════════════════

def test_format_anomalies_text(ledger_db):
    as_of = date(2026, 8, 17)
    _seed_calendar(ledger_db, as_of)
    for i in range(30):
        _tx(ledger_db, "expense", 1_500_000, as_of - timedelta(days=i), "Food", description="Spike")
    result = an.detect_anomalies(ledger_db, as_of=as_of)
    text = an.format_anomalies_text(result)
    assert "Anomali Keuangan" in text
    assert "Kenaikan kategori" in text
    assert "Food" in text
    assert "3.0x" in text
    assert "Rata-rata harian" in text


def test_format_anomalies_text_clean(ledger_db):
    result = an.detect_anomalies(ledger_db, as_of=date(2026, 8, 17))
    text = an.format_anomalies_text(result)
    assert "Anomali Keuangan" in text
    assert "Tidak ada anomali terdeteksi" in text
