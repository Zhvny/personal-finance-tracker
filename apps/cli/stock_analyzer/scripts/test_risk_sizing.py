
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from apps.cli.stock_analyzer.domain.risk import RiskManager


def simulate_sizing():
    rm = RiskManager()
    account_size = 100_000_000
    base_risk = 0.02
    sl_base_multiplier = 2.0 # From config

    scenarios = [
        {"name": "Blue Chip (Low Vol)", "price": 10000, "atr": 200, "score": 9.5, "vr": 0.5},
        {"name": "Mid Cap (Normal Vol)", "price": 5000, "atr": 250, "score": 8.5, "vr": 1.0},
        {"name": "Crypto (High Vol)", "price": 1000, "atr": 200, "score": 8.0, "vr": 2.0},
        {"name": "Extreme/Shitcoin", "price": 100, "atr": 50, "score": 7.0, "vr": 3.0},
        {"name": "Low Confidence Setup", "price": 10000, "atr": 200, "score": 6.0, "vr": 1.0},
    ]

    print(f"{'Scenario':<25} | {'Risk%':<6} | {'SL Mult':<7} | {'SL Dist%':<8} | {'Pos Size':<10} | {'Notional%':<10}")
    print("-" * 100)

    for s in scenarios:
        price = s['price']
        atr = s['atr']
        score = s['score']
        vr = s['vr']

        wr, rr = rm.get_strategy_performance(score)

        # New Logic: Dynamic Risk
        dynamic_risk = rm.calculate_dynamic_risk(score, wr, rr, base_risk)

        # New Logic: Vol-Adjusted SL
        sl_mult = sl_base_multiplier
        vol_regime = "HIGH" if vr > 1.3 else ("LOW" if vr < 0.7 else "NORMAL")
        if vol_regime == "HIGH": sl_mult *= 1.2
        elif vol_regime == "LOW": sl_mult *= 0.9

        sl = price - (sl_mult * atr)
        if sl >= price: sl = price * 0.96

        sl_dist_pct = (price - sl) / price * 100
        pos_size = rm.calculate_position_size(account_size, dynamic_risk, price, sl, max_notional_pct=0.35)
        notional_pct = (pos_size * price) / account_size * 100

        print(f"{s['name']:<25} | {dynamic_risk*100:>5.1f}% | {sl_mult:>7.1f} | {sl_dist_pct:>7.1f}% | {int(pos_size):<10} | {notional_pct:>9.1f}%")


    print("\n--- Kelly Criterion Check ---")
    scores = [6.0, 7.0, 8.0, 9.0, 10.0]
    for sc in scores:
        wr, rr = rm.get_strategy_performance(sc)
        kelly = rm.calculate_kelly_criterion(wr, rr)
        print(f"Score: {sc:<4} | WinRate: {wr*100:>3.0f}% | RR: {rr:<3} | Kelly: {kelly*100:>5.1f}%")

if __name__ == "__main__":
    simulate_sizing()
