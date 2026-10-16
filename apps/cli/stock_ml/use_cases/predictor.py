import logging

from stock_ml.domain.models import PredictionResult
from stock_ml.infrastructure.data_loader import DataLoader


class StockPredictor:
    def __init__(self, data_loader: DataLoader):
        self.data_loader = data_loader

    def get_all_predictions(self) -> list[PredictionResult]:
        df = self.data_loader.load_summary()
        if df.empty:
            logging.warning("[StockPredictor] Summary file is empty or not found.")
            return []

        # Ensure all required columns are handled safely
        df = df.fillna(0)

        results = []
        for _, row in df.iterrows():
            try:
                # Use .get() everywhere to prevent KeyError
                ticker = str(row.get('ticker', 'UNKNOWN'))
                category = str(row.get('category', 'us'))

                # In v2.0 we have precision_buy and precision_sell
                # But GUI still wants a generic 'precision_high_conf' field
                # in the domain model if it's old code.
                # However, I updated models.py to have specific fields.

                results.append(PredictionResult(
                    ticker=ticker,
                    category=category,
                    global_acc=float(row.get('global_acc', 0)),
                    precision_buy=float(row.get('precision_buy', 0)),
                    precision_sell=float(row.get('precision_sell', 0)),
                    n_sniper_buy=int(row.get('n_sniper_buy', 0)),
                    n_sniper_sell=int(row.get('n_sniper_sell', 0)),
                    latest_signal=str(row.get('latest_signal', 'NEUTRAL')),
                    p_sell=float(row.get('p_sell', 0)),
                    p_neutral=float(row.get('p_neutral', 0.33)),
                    p_buy=float(row.get('p_buy', 0)),
                    timestamp=str(row.get('timestamp', ''))
                ))
            except Exception as e:
                logging.error(f"[StockPredictor] Error mapping row for {row.get('ticker')}: {e}")
                continue
        return results
