import os
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
RESULTS_HONEST = _ROOT / "data" / "results_honest" / "honest_summary.csv"
DASHBOARD_PATH = _HERE / "index.html"

def generate_dashboard():
    if not os.path.exists(RESULTS_HONEST):
        print("Summary not found."); return

    df = pd.read_csv(RESULTS_HONEST)

    # Stats for the header
    n_models = len(df)
    avg_prec = df['precision'].mean() * 100
    total_signals = df['n_signals'].sum()

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>SHPIS // ELITE SNIPER AUDIT</title>
    <style>
        body {{ background: #000; color: #eee; font-family: monospace; padding: 40px; }}
        .stats {{ display: flex; gap: 40px; margin-bottom: 40px; }}
        .stat-card {{ background: #111; padding: 20px 40px; border-radius: 12px; border: 1px solid #222; border-top: 4px solid #00b8d4; }}
        .stat-lbl {{ color: #555; font-size: 10px; text-transform: uppercase; margin-bottom: 8px; }}
        .stat-val {{ font-size: 32px; font-weight: bold; color: #00b8d4; }}
        
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px 15px; border-bottom: 1px solid #111; text-align: left; }}
        th {{ background: #080808; color: #555; text-transform: uppercase; font-size: 10px; letter-spacing: 1px; }}
        .ticker {{ font-weight: bold; color: #fff; font-size: 14px; }}
        .badge {{ padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 10px; text-transform: uppercase; }}
        .sig-buy {{ background: #004d00; color: #00ff00; border: 1px solid #00ff00; }}
        .sig-sell {{ background: #4d0000; color: #ff0000; border: 1px solid #ff0000; }}
        .neutral {{ color: #555; border: 1px solid #333333; }}
        tr:hover {{ background: #050505; }}
    </style>
</head>
<body>
    <h1 style="letter-spacing: -1px; margin-bottom: 5px;">SHPIS_ELITE_ENGINE_AUDIT</h1>
    <div style="color:#555; font-size:12px; margin-bottom: 30px;">Automated Backtest Results | Confidence Threshold: 0.70+</div>

    <div class="stats">
        <div class="stat-card"><div class="stat-lbl">Active Models</div><div class="stat-val">{n_models}</div></div>
        <div class="stat-card"><div class="stat-lbl">Avg. Precision</div><div class="stat-val">{avg_prec:.1f}%</div></div>
        <div class="stat-card"><div class="stat-lbl">Total Signals</div><div class="stat-val">{total_signals:,}</div></div>
    </div>
    
    <table>
        <thead>
            <tr>
                <th>Asset</th>
                <th>Category</th>
                <th>Precision</th>
                <th>Lifetime Signals</th>
                <th>Latest Status</th>
                <th>Confidence</th>
            </tr>
        </thead>
        <tbody>
    """

    for _, r in df.iterrows():
        sig = str(r['signal'])
        cls = "sig-buy" if "BUY" in sig else ("sig-sell" if "SELL" in sig else "neutral")

        html += f"""
            <tr>
                <td class="ticker">{r['ticker']}</td>
                <td style="color:#555">{r['category']}</td>
                <td style="color:#00b8d4; font-weight: bold;">{r['precision']*100:.1f}%</td>
                <td>{int(r['n_signals']):,}</td>
                <td><span class="badge {cls}">{sig}</span></td>
                <td>{r['prob']*100:.1f}%</td>
            </tr>
        """

    html += "</tbody></table></body></html>"
    with open(DASHBOARD_PATH, "w") as f: f.write(html)
    print("✓ Dashboard v2.1 Generated")

if __name__ == "__main__":
    generate_dashboard()
