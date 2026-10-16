import os
import sys
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template

# Setup paths to import from stock_analyzer and shared packages
_HERE = Path(__file__).resolve().parent
_APPS = _HERE.parent
_ROOT = _APPS.parent
STOCK_ANALYZER_PATH = _APPS / "stock_analyzer"

if str(_APPS) not in sys.path:
    sys.path.insert(0, str(_APPS))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from stock_analyzer.adapters.cleaner import DataCleaner
from stock_analyzer.adapters.fetcher import DataFetcher
from stock_analyzer.adapters.indicators import IndicatorEngine
from stock_analyzer.domain.config import AppConfig
from stock_analyzer.domain.scoring import ScoringEngine
from stock_analyzer.use_cases.analyzer import StockAnalyzer

app = Flask(__name__,
            template_folder='web/templates',
            static_folder='web/static')

CSV_ML_PATH = _ROOT / "data" / "results_honest" / "honest_summary.csv"

# Global Analyzer Instance
analyzer = StockAnalyzer(DataFetcher(), DataCleaner(), IndicatorEngine(), ScoringEngine(), AppConfig.load(str(STOCK_ANALYZER_PATH / "config.yaml")))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    if not os.path.exists(CSV_ML_PATH):
        return jsonify([])

    df_ml = pd.read_csv(CSV_ML_PATH)
    data = df_ml.where(pd.notnull(df_ml), None).to_dict(orient='records')
    return jsonify(data)

@app.route('/api/analyze/<ticker>')
def analyze_ticker(ticker):
    print(f"Deep Analyzing: {ticker}")
    res = analyzer.analyze_ticker(ticker.upper())
    if not res:
        return jsonify({"error": "Failed to analyze ticker"}), 404

    # Map StockResult to a clean dict for JSON
    return jsonify({
        "ticker": res.ticker,
        "price": res.current_price,
        "score": res.score,
        "signal": res.signal.value,
        "support": res.support,
        "resistance": res.resistance,
        "stop_loss": res.stop_loss,
        "take_profit": res.take_profit,
        "win_rate": f"{res.win_rate*100:.1f}%",
        "rr_ratio": res.risk_reward_ratio,
        "kelly": f"{res.kelly_fraction*100:.1f}%",
        "pos_size": res.position_size,
        "css": res.css,
        "mrzg": res.mrzg
    })

if __name__ == '__main__':
    print("\n--- SHPIS + STOCK ANALYZER MERGED SYSTEM ---")
    print("Localhost: http://127.0.0.1:5000")
    if not sys.stdin.isatty() or os.environ.get("TERM") == "dumb":
        print("Flask server (Skipped in non-TTY/headless environment)")
        sys.exit(0)
    app.run(debug=False, port=5000)
