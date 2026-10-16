from datetime import datetime, timedelta
from typing import Dict, List

import yfinance as yf

try:
    from packages.core.utils.symbol_utils import SymbolFormatter
except ImportError:
    try:
        from apps.cli.stock_analyzer.infrastructure.symbol_utils import SymbolFormatter
    except ImportError:
        SymbolFormatter = None

class HistoricalDataService:

    TROY_OUNCE_TO_GRAM = 31.1034768

    def get_weekly_history(self, ticker: str, asset_type: str, start_date: datetime, fx_service=None) -> List[Dict]:
        """Fetch historical data from buy_date to now."""

        if asset_type == 'gold' and fx_service:
            from apps.cli.investment_tracker.services.gold_service import GoldPriceService
            gold_service = GoldPriceService(fx_service)
            return gold_service.get_historical_idr(ticker, start_date)

        yf_ticker = self._map_ticker(ticker, asset_type)
        end_date = datetime.now()

        # Ensure we have at least some range, but respect the buy date
        # If buy_date is today, we might need a small buffer to get any data
        fetch_start = start_date
        if (end_date - fetch_start).days < 2:
            fetch_start = end_date - timedelta(days=7) # Get at least a week of context

        try:
            # Use interval='1d' to get granular data, then resample
            df = yf.download(yf_ticker, start=fetch_start.strftime('%Y-%m-%d'),
                            end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                            progress=False, interval='1d')

            if df.empty:
                # Try a slightly wider range if empty (e.g. IPO cases or data gaps)
                df = yf.download(yf_ticker, period="1mo", progress=False)
                if df.empty:
                    raise ValueError(f"No data for {yf_ticker}")

            # Use 'Adj Close' for stocks if available, otherwise 'Close'
            col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'

            # Resample to weekly but KEEP the last data point (today's/yesterday's close)
            # Resampling 'W' might skip the current partial week.
            # We'll use daily data and filter for weekly points + the absolute latest point.
            df = df[[col]].dropna()

            # Simple heuristic: take every 7th day + the very last day
            indices = list(range(0, len(df), 7))
            if (len(df) - 1) not in indices:
                indices.append(len(df) - 1)

            selected_df = df.iloc[indices]

            history = []
            for date, row in selected_df.iterrows():
                val = row[col]
                if hasattr(val, 'item'): val = val.item()

                # Untuk gold, convert $/oz ke $/gram (if not handled by gold_service)
                if asset_type == 'gold':
                    val = val / self.TROY_OUNCE_TO_GRAM

                history.append({
                    'date': date.to_pydatetime(),
                    'close': float(val)
                })

            return history

        except Exception as e:
            raise ValueError(f"Failed to fetch {yf_ticker}: {e}")

    def _map_ticker(self, ticker: str, asset_type: str) -> str:
        # Use SymbolFormatter if available
        if SymbolFormatter:
            norm = SymbolFormatter.normalize(ticker)
            if norm != ticker:
                return norm

        # Fallback to legacy mapping
        if asset_type == 'gold':
            return 'GC=F' if ticker.upper() in ['XAU', 'GOLD'] else 'SI=F'
        elif asset_type == 'crypto':
            return f"{ticker}-USD"
        return ticker

    def generate_pl_journey(self, history: List[Dict], buy_price: float,
                          quantity: float, buy_date: datetime, ticker: str = "") -> str:
        """Horizontal bar journey"""

        if not history:
            return "No data available."

        symbol = "Rp" if ticker.upper().endswith(".JK") else "$"
        buy_value = buy_price * quantity

        lines = []
        lines.append(f"\n {history[0]['date'].strftime('%d %b %Y').upper()} P/L JOURNEY")
        lines.append(f"Buy: {symbol}{buy_price:,.2f}/unit × {quantity} = {symbol}{buy_value:,.2f}")
        lines.append("")

        all_values = [h['close'] * quantity for h in history]
        max_value = max(all_values + [buy_value])
        min_value = min(all_values + [buy_value])

        best_pl = -999999
        worst_pl = 999999
        rows = []

        for point in history:
            current_value = point['close'] * quantity
            pl = current_value - buy_value
            pl_pct = (pl / buy_value) * 100 if buy_value else 0

            rows.append({
                'date': point['date'],
                'value': current_value,
                'pl': pl,
                'pl_pct': pl_pct,
                'is_buy': abs((point['date'] - buy_date).days) < 3
            })

            best_pl = max(best_pl, pl)
            worst_pl = min(worst_pl, pl)

        bar_width = 10

        for row in rows:
            if row['value'] >= buy_value:
                fill = int(((row['value'] - buy_value) / (max_value - buy_value)) * bar_width) if max_value != buy_value else 0
                fill = max(1, fill)
                bar = "█" * fill + "░" * (bar_width - fill)
            else:
                fill = int(((buy_value - row['value']) / (buy_value - min_value)) * bar_width) if buy_value != min_value else 0
                fill = max(1, fill)
                bar = "░" * (bar_width - fill) + "█" * fill

            date_str = row['date'].strftime('%d/%m')
            value_str = f"{symbol}{row['value']:,.2f}"

            if row['pl'] >= 0:
                pl_str = f"+{symbol}{row['pl']:,.2f}"
                pct_str = f"+{row['pl_pct']:.1f}%"
                emoji = ""
            else:
                pl_str = f"-{symbol}{abs(row['pl']):,.2f}"
                pct_str = f"{row['pl_pct']:.1f}%"
                emoji = ""

            notes = []
            if row['is_buy']:
                notes.append("(BUY)")
            if row['pl'] == best_pl and best_pl > 0:
                notes.append(" BEST")
            if row['pl'] == worst_pl and worst_pl < 0:
                notes.append(" WORST")

            note_str = " ".join(notes)
            lines.append(f"{date_str}  {bar} {value_str:>10}  ({pl_str}, {pct_str}) {emoji} {note_str}")

        final = rows[-1]
        lines.append("")
        if final['pl'] >= 0:
            lines.append(f"CURRENT: +{symbol}{final['pl']:,.2f} (+{final['pl_pct']:.1f}%)")
        else:
            lines.append(f"CURRENT: -{symbol}{abs(final['pl']):,.2f} ({final['pl_pct']:.1f}%)")

        return "\n".join(lines)
