
import sys
from pathlib import Path

# Add apps directory to sys.path
_HERE = Path(__file__).resolve()
_APPS_DIR = _HERE.parent.parent.parent
sys.path.insert(0, str(_APPS_DIR))


from apps.cli.stock_analyzer.domain.risk import RiskManager


def simulate_risk(ticker_name, price, atr, score, win_rate=None, rr=None):
    rm = RiskManager()

    # 1. Get WR/RR if not provided
    if win_rate is None or rr is None:
        win_rate, rr = rm.get_strategy_performance(score)

    # 2. Calculate dynamic risk
    risk_pct = rm.calculate_dynamic_risk(score, win_rate, rr)

    # 3. Calculate Stop Loss (Heuristic: 2.2 * ATR, same as analyzer.py)
    # Note: We simulate the logic found in analyzer.py
    stop_loss = price - (2.2 * atr)
    if stop_loss >= price: stop_loss = price * 0.96

    # 4. Calculate Position Size
    balance = 100_000_000 # 100jt IDR
    units = rm.calculate_position_size(balance, risk_pct, price, stop_loss)
    notional = units * price
    notional_pct = (notional / balance) * 100

    # 5. Kelly Criterion
    kelly = rm.calculate_kelly_criterion(win_rate, rr)

    print(f"\n--- Simulation: {ticker_name} ---")
    print(f"Price: {price:,.2f} | ATR: {atr:,.2f} ({ (atr/price)*100:.2f}%)")
    print(f"Score: {score} | WR: {win_rate*100:.1f}% | RR: {rr}")
    print(f"Kelly: {kelly*100:.1f}% | Suggested Risk: {risk_pct*100:.2f}%")
    print(f"Stop Loss: {stop_loss:,.2f} ({( (price-stop_loss)/price )*100:.2f}% distance)")
    print(f"Position Size: {units:,.0f} units")
    print(f"Notional Value: {notional:,.2f} ({notional_pct:.1f}% of balance)")

    if notional_pct >= 29.9:
        print("[!] CAP HIT: Notional hit the 30% safety ceiling.")

def main():
    # Case 1: Blue Chip (Low Volatility)
    # BBCA: Price 10000, ATR 150 (1.5%)
    simulate_risk("BBCA (Blue Chip)", 10000, 150, 9.0)

    # Case 2: Crypto (High Volatility)
    # BTC: Price 60000, ATR 3000 (5%)
    simulate_risk("BTC (High Vol)", 60000, 3000, 9.0)

    # Case 3: "Gorengan" (Extreme Volatility)
    # Small cap: Price 500, ATR 100 (20%)
    simulate_risk("GORENGAN (Extreme Vol)", 500, 100, 9.0)

    # Case 4: Weak setup (Low Score)
    simulate_risk("BBCA (Weak Setup)", 10000, 150, 6.0)

    # Case 5: Over-leverage test (Max WR, Max RR)
    simulate_risk("THE PERFECT TRADE", 10000, 500, 10.0, win_rate=0.85, rr=5.0)

if __name__ == "__main__":
    main()
