"""
tests/unit/test_evaluation_engine.py
=====================================
Unit tests for EvaluationEngine (evaluation_engine.py) — 0% → target ≥80% coverage.

All database (DatabaseManager) and yfinance calls are mocked so tests are
fully offline and deterministic.

Covers:
  - evaluate_pending_predictions() : no-op on empty, processes batch, updates metrics
  - _evaluate_one()                : BUY/SELL/HOLD logic, correct/incorrect scoring,
                                     missing price_at_prediction fallback, future eval_date guard
  - _fetch_price_at()              : normal return, empty df, exception handling
  - _refresh_performance_metrics() : per-agent stats aggregation, zero-count skip
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from apps.cli.investment_tracker.services.evaluation_engine import EvaluationEngine

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures & Factories
# ─────────────────────────────────────────────────────────────────────────────

def make_pred(
    ticker="BBCA.JK",
    prediction="BUY",
    price_at_pred=10_000.0,
    confidence=0.8,
    hours_ago=48,
    pred_id=1,
    agent_name="TestAgent",
) -> dict:
    """Build a mock prediction row dict."""
    return {
        "id": pred_id,
        "ticker": ticker,
        "prediction": prediction,
        "price_at_prediction": price_at_pred,
        "confidence": confidence,
        "timestamp": datetime.now() - timedelta(hours=hours_ago),
        "agent_name": agent_name,
    }


def make_close_df(price: float) -> pd.DataFrame:
    """Build a minimal yfinance-like DataFrame with a single Close row."""
    idx = pd.to_datetime(["2025-06-16"])
    return pd.DataFrame({"Close": [price]}, index=idx)


@pytest.fixture
def engine() -> EvaluationEngine:
    return EvaluationEngine()


# ─────────────────────────────────────────────────────────────────────────────
# 1. evaluate_pending_predictions()
# ─────────────────────────────────────────────────────────────────────────────

class TestEvaluatePendingPredictions:
    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.query")
    def test_returns_zero_when_no_pending(self, mock_query, engine):
        mock_query.return_value = []
        result = engine.evaluate_pending_predictions()
        assert result == 0

    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.query")
    def test_db_error_returns_zero(self, mock_query, engine):
        mock_query.side_effect = Exception("DB connection failed")
        result = engine.evaluate_pending_predictions()
        assert result == 0

    @patch.object(EvaluationEngine, "_refresh_performance_metrics")
    @patch.object(EvaluationEngine, "_evaluate_one", return_value=True)
    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.query")
    def test_processes_all_pending_and_refreshes(self, mock_query, mock_eval, mock_refresh, engine):
        mock_query.return_value = [make_pred(pred_id=1), make_pred(pred_id=2)]
        result = engine.evaluate_pending_predictions()
        assert result == 2
        assert mock_eval.call_count == 2
        mock_refresh.assert_called_once()

    @patch.object(EvaluationEngine, "_refresh_performance_metrics")
    @patch.object(EvaluationEngine, "_evaluate_one", return_value=False)
    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.query")
    def test_no_refresh_when_zero_evaluated(self, mock_query, mock_eval, mock_refresh, engine):
        mock_query.return_value = [make_pred(pred_id=1)]
        result = engine.evaluate_pending_predictions()
        assert result == 0
        mock_refresh.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# 2. _evaluate_one() — prediction correctness logic
# ─────────────────────────────────────────────────────────────────────────────

class TestEvaluateOne:
    # 2a. BUY correctness
    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.execute")
    @patch.object(EvaluationEngine, "_fetch_price_at")
    def test_buy_correct_when_price_rises(self, mock_fetch, mock_exec, engine):
        """BUY → correct when price rose > 0.5%"""
        pred = make_pred(prediction="BUY", price_at_pred=10_000, confidence=1.0)
        mock_fetch.return_value = 10_200.0  # +2% → correct
        result = engine._evaluate_one(pred)
        assert result is True
        # Score should be positive
        args = mock_exec.call_args[0][1]  # (pred_id, actual_price, pct, correct, score)
        assert args[3] is True
        assert args[4] > 0

    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.execute")
    @patch.object(EvaluationEngine, "_fetch_price_at")
    def test_buy_incorrect_when_price_drops(self, mock_fetch, mock_exec, engine):
        """BUY → incorrect when price dropped"""
        pred = make_pred(prediction="BUY", price_at_pred=10_000, confidence=0.5)
        mock_fetch.return_value = 9_800.0  # -2% → wrong
        result = engine._evaluate_one(pred)
        assert result is True
        args = mock_exec.call_args[0][1]
        assert args[3] is False
        assert args[4] < 0  # Negative score for wrong + penalized confidence

    # 2b. SELL correctness
    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.execute")
    @patch.object(EvaluationEngine, "_fetch_price_at")
    def test_sell_correct_when_price_drops(self, mock_fetch, mock_exec, engine):
        pred = make_pred(prediction="SELL", price_at_pred=10_000, confidence=0.7)
        mock_fetch.return_value = 9_800.0  # -2% → correct
        result = engine._evaluate_one(pred)
        assert result is True
        args = mock_exec.call_args[0][1]
        assert args[3] is True

    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.execute")
    @patch.object(EvaluationEngine, "_fetch_price_at")
    def test_sell_incorrect_when_price_rises(self, mock_fetch, mock_exec, engine):
        pred = make_pred(prediction="SELL", price_at_pred=10_000, confidence=0.9)
        mock_fetch.return_value = 10_200.0  # +2% → wrong
        result = engine._evaluate_one(pred)
        assert result is True
        args = mock_exec.call_args[0][1]
        assert args[3] is False

    # 2c. HOLD correctness
    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.execute")
    @patch.object(EvaluationEngine, "_fetch_price_at")
    def test_hold_correct_within_band(self, mock_fetch, mock_exec, engine):
        """HOLD → correct if change within [-0.5%, +0.5%]"""
        pred = make_pred(prediction="HOLD", price_at_pred=10_000, confidence=0.6)
        mock_fetch.return_value = 10_020.0  # +0.2% → within band
        result = engine._evaluate_one(pred)
        args = mock_exec.call_args[0][1]
        assert args[3] is True

    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.execute")
    @patch.object(EvaluationEngine, "_fetch_price_at")
    def test_hold_incorrect_outside_band(self, mock_fetch, mock_exec, engine):
        pred = make_pred(prediction="HOLD", price_at_pred=10_000, confidence=0.6)
        mock_fetch.return_value = 10_200.0  # +2% → outside band → wrong
        result = engine._evaluate_one(pred)
        args = mock_exec.call_args[0][1]
        assert args[3] is False

    # 2d. Missing price_at_prediction fallback
    @patch.object(EvaluationEngine, "_fetch_price_at", return_value=None)
    def test_returns_false_when_fallback_price_unavailable(self, mock_fetch, engine):
        pred = make_pred(price_at_pred=None)
        result = engine._evaluate_one(pred)
        assert result is False

    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.execute")
    @patch.object(EvaluationEngine, "_fetch_price_at")
    def test_fallback_fetches_price_at_timestamp(self, mock_fetch, mock_exec, engine):
        """When price_at_prediction is None, falls back to _fetch_price_at(timestamp)"""
        pred = make_pred(price_at_pred=None)
        # First call (fallback) returns 10000, second call (actual) returns 10200
        mock_fetch.side_effect = [10_000.0, 10_200.0]
        result = engine._evaluate_one(pred)
        assert result is True
        assert mock_fetch.call_count == 2

    # 2e. Future eval_date guard
    @patch.object(EvaluationEngine, "_fetch_price_at")
    def test_skips_prediction_with_future_eval_date(self, mock_fetch, engine):
        """If prediction is only 1 hour old, eval_date is in the future → skip"""
        pred = make_pred(hours_ago=1, price_at_pred=10_000)
        result = engine._evaluate_one(pred)
        assert result is False
        mock_fetch.assert_not_called()  # Should not even try to fetch

    # 2f. No actual price → skip
    @patch.object(EvaluationEngine, "_fetch_price_at")
    def test_skips_when_actual_price_unavailable(self, mock_fetch, engine):
        pred = make_pred(price_at_pred=10_000)
        mock_fetch.return_value = None  # actual price unavailable
        result = engine._evaluate_one(pred)
        assert result is False

    # 2g. DB insert failure
    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.execute")
    @patch.object(EvaluationEngine, "_fetch_price_at", return_value=10_200.0)
    def test_returns_false_on_db_insert_failure(self, mock_fetch, mock_exec, engine):
        mock_exec.side_effect = Exception("DB insert failed")
        pred = make_pred(price_at_pred=10_000, prediction="BUY")
        result = engine._evaluate_one(pred)
        assert result is False

    # 2h. Score math
    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.execute")
    @patch.object(EvaluationEngine, "_fetch_price_at")
    def test_score_correct_formula(self, mock_fetch, mock_exec, engine):
        """Score = 1.0 * confidence if correct"""
        pred = make_pred(prediction="BUY", price_at_pred=10_000, confidence=0.75)
        mock_fetch.return_value = 10_200.0  # correct BUY
        engine._evaluate_one(pred)
        args = mock_exec.call_args[0][1]
        expected_score = 1.0 * 0.75
        assert args[4] == pytest.approx(expected_score)

    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.execute")
    @patch.object(EvaluationEngine, "_fetch_price_at")
    def test_score_penalty_formula(self, mock_fetch, mock_exec, engine):
        """Score = -1.0 * (1 + confidence) if incorrect"""
        pred = make_pred(prediction="BUY", price_at_pred=10_000, confidence=0.75)
        mock_fetch.return_value = 9_800.0  # wrong BUY
        engine._evaluate_one(pred)
        args = mock_exec.call_args[0][1]
        expected_score = -1.0 * (1.0 + 0.75)
        assert args[4] == pytest.approx(expected_score)

    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.execute")
    @patch.object(EvaluationEngine, "_fetch_price_at")
    def test_missing_confidence_defaults_to_half(self, mock_fetch, mock_exec, engine):
        """If 'confidence' key missing in pred dict, default is 0.5"""
        pred = make_pred(prediction="BUY", price_at_pred=10_000)
        del pred["confidence"]  # Remove key
        mock_fetch.return_value = 10_200.0
        engine._evaluate_one(pred)
        args = mock_exec.call_args[0][1]
        # confidence defaults to 0.5 → score = 0.5
        assert args[4] == pytest.approx(0.5)


# ─────────────────────────────────────────────────────────────────────────────
# 3. _fetch_price_at()
# ─────────────────────────────────────────────────────────────────────────────

class TestFetchPriceAt:
    @patch("apps.cli.investment_tracker.services.evaluation_engine.yf.download")
    def test_returns_first_close(self, mock_dl, engine):
        mock_dl.return_value = make_close_df(10_500.0)
        result = engine._fetch_price_at("BBCA.JK", datetime(2025, 6, 16, 10, 0))
        assert result == pytest.approx(10_500.0)

    @patch("apps.cli.investment_tracker.services.evaluation_engine.yf.download")
    def test_returns_none_for_empty_df(self, mock_dl, engine):
        mock_dl.return_value = pd.DataFrame()
        result = engine._fetch_price_at("INVALID", datetime(2025, 6, 16))
        assert result is None

    @patch("apps.cli.investment_tracker.services.evaluation_engine.yf.download")
    def test_returns_none_on_exception(self, mock_dl, engine):
        mock_dl.side_effect = Exception("Network error")
        result = engine._fetch_price_at("BBCA.JK", datetime(2025, 6, 16))
        assert result is None

    @patch("apps.cli.investment_tracker.services.evaluation_engine.yf.download")
    def test_correct_date_range_passed_to_yfinance(self, mock_dl, engine):
        mock_dl.return_value = make_close_df(1000.0)
        target = datetime(2025, 6, 16, 10, 0)
        engine._fetch_price_at("AAPL", target)
        call_kwargs = mock_dl.call_args
        start = call_kwargs[1].get("start") or call_kwargs[0][1]
        end   = call_kwargs[1].get("end")   or call_kwargs[0][2]
        assert start == "2025-06-16"
        # end should be 3 days later
        assert end == "2025-06-19"


# ─────────────────────────────────────────────────────────────────────────────
# 4. _refresh_performance_metrics()
# ─────────────────────────────────────────────────────────────────────────────

class TestRefreshPerformanceMetrics:
    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.execute")
    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.query")
    def test_updates_performance_for_each_agent(self, mock_query, mock_exec, engine):
        mock_query.side_effect = [
            # First call: distinct agents
            [{"agent_name": "Alpha"}, {"agent_name": "Beta"}],
            # Second call: stats for Alpha
            [{"total": 5, "accuracy": 0.8, "avg_score": 0.6, "avg_ret": 0.02}],
            # Third call: stats for Beta
            [{"total": 3, "accuracy": 0.67, "avg_score": 0.4, "avg_ret": 0.01}],
        ]
        engine._refresh_performance_metrics()
        # Should execute 2 UPDATE statements
        assert mock_exec.call_count == 2

    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.execute")
    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.query")
    def test_skips_update_when_total_is_zero(self, mock_query, mock_exec, engine):
        mock_query.side_effect = [
            [{"agent_name": "EmptyAgent"}],
            [{"total": 0, "accuracy": None, "avg_score": None, "avg_ret": None}],
        ]
        engine._refresh_performance_metrics()
        mock_exec.assert_not_called()

    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.query")
    def test_handles_db_exception_gracefully(self, mock_query, engine):
        mock_query.side_effect = Exception("DB down")
        # Should not raise
        engine._refresh_performance_metrics()

    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.execute")
    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.query")
    def test_no_agents_means_no_updates(self, mock_query, mock_exec, engine):
        mock_query.return_value = []
        engine._refresh_performance_metrics()
        mock_exec.assert_not_called()

    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.execute")
    @patch("apps.cli.investment_tracker.services.evaluation_engine.DatabaseManager.query")
    def test_correct_params_passed_to_execute(self, mock_query, mock_exec, engine):
        mock_query.side_effect = [
            [{"agent_name": "Alpha"}],
            [{"total": 10, "accuracy": 0.9, "avg_score": 0.7, "avg_ret": 0.03}],
        ]
        engine._refresh_performance_metrics()
        assert mock_exec.called
        params = mock_exec.call_args[0][1]
        assert params[0] == pytest.approx(0.9)  # accuracy
        assert params[1] == pytest.approx(0.7)  # avg_score
        assert params[4] == "Alpha"             # agent_name
