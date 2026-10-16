import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import yfinance as yf

from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager


class EvaluationEngine:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def evaluate_pending_predictions(self):
        """
        Processes all predictions that are older than 24 hours and haven't been evaluated.
        """
        # Fetch predictions that are at least 24 hours old and not yet evaluated
        sql = """
            SELECT p.* 
            FROM audit.agent_predictions p
            LEFT JOIN audit.agent_outcomes o ON p.id = o.prediction_id
            WHERE o.prediction_id IS NULL
            AND p.timestamp < CURRENT_TIMESTAMP - INTERVAL '24 hours'
            ORDER BY p.timestamp ASC
            LIMIT 100
        """
        try:
            pending = DatabaseManager.query(sql)
            if not pending:
                return 0

            count = 0
            for pred in pending:
                if self._evaluate_one(pred):
                    count += 1

            # Refresh performance metrics after processing batch
            if count > 0:
                self._refresh_performance_metrics()

            return count
        except Exception as e:
            self.logger.error(f"Evaluation loop failed: {e}")
            return 0

    def _evaluate_one(self, pred: Dict[str, Any]) -> bool:
        ticker = pred['ticker']
        pred_id = pred['id']
        pred_type = pred['prediction'] # BUY, SELL, HOLD
        price_at_pred = pred['price_at_prediction']

        # In case price_at_prediction was not logged (fallback)
        if not price_at_pred:
             # Try to get price from that specific timestamp (approx)
             price_at_pred = self._fetch_price_at(ticker, pred['timestamp'])
             if not price_at_pred:
                 return False

        # Target evaluation date is timestamp + 24h
        eval_date = pred['timestamp'] + timedelta(hours=24)

        # If eval_date is in the future (safety check), skip
        if eval_date > datetime.now():
            return False

        actual_price = self._fetch_price_at(ticker, eval_date)
        if not actual_price:
            return False

        price_change_pct = (actual_price - price_at_pred) / price_at_pred

        # Logic:
        # BUY: Success if price rose > 0.5%
        # SELL: Success if price dropped > 0.5%
        # HOLD: Success if price moved within [-0.5%, 0.5%]

        correct = False
        if pred_type == "BUY":
            correct = price_change_pct > 0.005
        elif pred_type == "SELL":
            correct = price_change_pct < -0.005
        elif pred_type == "HOLD":
            correct = abs(price_change_pct) <= 0.005

        # Score calculation (-1.0 to 1.0)
        # Penalize confidence: if highly confident and wrong, score is lower
        confidence = pred.get('confidence', 0.5)
        if correct:
            score = 1.0 * confidence
        else:
            score = -1.0 * (1.0 + confidence) # Penalized for overconfidence

        try:
            sql = """
                INSERT INTO audit.agent_outcomes 
                (prediction_id, actual_price, actual_return_pct, correct, score)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (prediction_id) DO NOTHING
            """
            DatabaseManager.execute(sql, (pred_id, actual_price, price_change_pct, correct, score))
            return True
        except Exception as e:
            self.logger.error(f"Failed to save outcome for ID {pred_id}: {e}")
            return False

    def _fetch_price_at(self, ticker: str, target_dt: datetime) -> Optional[float]:
        """Fetches the closing price for a ticker as close as possible to target_dt."""
        try:
            # We fetch a 3-day window to ensure we catch a trading day
            start = target_dt.strftime('%Y-%m-%d')
            end = (target_dt + timedelta(days=3)).strftime('%Y-%m-%d')

            df = yf.download(ticker, start=start, end=end, progress=False)
            if df.empty:
                return None

            # Use the first available close after the target date
            return float(df['Close'].iloc[0])
        except Exception:
            return None

    def _refresh_performance_metrics(self):
        """Aggregates outcome data into agent_performance table."""
        try:
            # Clear/Reset or update only existing
            agents_sql = "SELECT DISTINCT agent_name FROM audit.agent_predictions"
            agents = DatabaseManager.query(agents_sql)

            for agent in agents:
                name = agent['agent_name']

                stats_sql = """
                    SELECT 
                        COUNT(*) as total,
                        AVG(CASE WHEN o.correct THEN 1.0 ELSE 0.0 END) as accuracy,
                        AVG(o.score) as avg_score,
                        AVG(o.actual_return_pct) as avg_ret
                    FROM audit.agent_predictions p
                    JOIN audit.agent_outcomes o ON p.id = o.prediction_id
                    WHERE p.agent_name = %s
                """
                stats = DatabaseManager.query(stats_sql, (name,))[0]

                if stats['total'] > 0:
                    update_sql = """
                        UPDATE audit.agent_performance
                        SET accuracy_h24 = %s,
                            sharpe_like_score = %s,
                            avg_return = %s,
                            win_rate = %s,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE agent_name = %s
                    """
                    DatabaseManager.execute(update_sql, (
                        stats['accuracy'],
                        stats['avg_score'],
                        stats['avg_ret'],
                        stats['accuracy'],
                        name
                    ))
        except Exception as e:
            self.logger.error(f"Performance refresh failed: {e}")

if __name__ == "__main__":
    # Test run
    logging.basicConfig(level=logging.INFO)
    engine = EvaluationEngine()
    count = engine.evaluate_pending_predictions()
    print(f"Evaluated {count} predictions.")
