import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
# Find the directory that contains 'stock_analyzer'
_P = _HERE.parent
while _P.name != "stock_analyzer" and _P.parent != _P:
    _P = _P.parent
_PROJECT_ROOT = str(_P.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import json

# Entry prices as of Jan-Feb 2026 reference baselines
portfolio = [
    {"ticker": "AMZN",     "entry": 208.62,   "date": "2026-02-24", "sl": 195.0,  "tp": 240.0},
    {"ticker": "JNJ",      "entry": 238.53,   "date": "2026-04-07", "sl": 220.0,  "tp": 270.0},
    {"ticker": "GC=F",     "entry": 2280.0,   "date": "2026-01-01", "sl": 2100.0, "tp": 2500.0}, # Gold
    {"ticker": "CL=F",     "entry": 85.0,     "date": "2026-01-01", "sl": 75.0,   "tp": 110.0},  # Oil
    {"ticker": "SI=F",     "entry": 24.5,     "date": "2026-01-01", "sl": 22.0,   "tp": 30.0},   # Silver
    {"ticker": "USDIDR=X", "entry": 16500.0,  "date": "2026-01-01", "sl": 16000.0, "tp": 17500.0},
    {"ticker": "EURIDR=X", "entry": 18500.0,  "date": "2026-01-01", "sl": 18000.0, "tp": 19500.0},
    {"ticker": "JPYIDR=X", "entry": 105.0,    "date": "2026-01-01", "sl": 100.0,   "tp": 115.0}
]

with open('portfolio_fix.json', 'w') as f:
    json.dump(portfolio, f, indent=4)
