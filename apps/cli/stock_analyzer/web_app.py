import logging
import sys
from pathlib import Path

# --- LOGGING SANITIZATION ---
logging.getLogger("asyncio").setLevel(logging.CRITICAL)
logging.getLogger("root").setLevel(logging.ERROR)
logging.getLogger("api.service.stock").setLevel(logging.ERROR)

_HERE = Path(__file__).resolve()
# Find the directory that contains 'stock_analyzer'
_P = _HERE.parent
while _P.name != "stock_analyzer" and _P.parent != _P:
    _P = _P.parent
_PROJECT_ROOT = str(_P.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import re
import secrets
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# Add project root to sys.path
ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from apps.cli.stock_analyzer.adapters.cleaner import DataCleaner
from apps.cli.stock_analyzer.adapters.fetcher import DataFetcher
from apps.cli.stock_analyzer.adapters.fred_fetcher import FREDFetcher
from apps.cli.stock_analyzer.adapters.indicators import IndicatorEngine
from apps.cli.stock_analyzer.domain.config import AppConfig
from apps.cli.stock_analyzer.domain.portfolio_manager import PortfolioManager
from apps.cli.stock_analyzer.domain.scoring import ScoringEngine
from apps.cli.stock_analyzer.use_cases.analyzer import StockAnalyzer


# --- SECURITY LAYER ---
def validate_ticker(ticker):
    """Input Sanitization: Strict regex for tickers."""
    return re.match(r"^[A-Z0-9.\-=]{1,15}$", ticker.upper())

def check_security(config):
    """Basic Security Measures: IP Whitelist & Token."""
    if not config.security_enabled:
        return True

    # 1. IP Whitelist (Note: st.context.headers is limited in some environments)
    if config.ip_whitelist_enabled:
        client_ip = st.context.headers.get("X-Forwarded-For", "127.0.0.1").split(",")[0]
        if client_ip not in config.allowed_ips:
            st.error(f"Access Denied: IP {client_ip} not whitelisted.")
            return False

    # 2. Token Handshake
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        with st.form("login"):
            token = st.text_input("Access Token", type="password")
            if st.form_submit_button("Authenticate"):
                if secrets.compare_digest(token, config.access_token):
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid Token")
            return False
    return True

# --- UI CONFIG ---
st.set_page_config(page_title="CORE", page_icon="📉", layout="wide")

# Minimalist Bloomberg-style CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #000000;
        color: #d1d1d1;
        font-family: 'JetBrains Mono', monospace;
    }
    .stMetric {
        background-color: #000000;
        border: 1px solid #222;
        padding: 10px;
    }
    div[data-testid="stSidebar"] {
        background-color: #000000;
        border-right: 1px solid #222;
    }
    .stDataFrame {
        border: 1px solid #222;
    }
    h1, h2, h3 {
        color: #ffffff;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    .status-bar {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: #111;
        color: #555;
        padding: 2px 10px;
        font-size: 10px;
        border-top: 1px solid #222;
        z-index: 999;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def get_macro_context(_config):
    fred = FREDFetcher(_config)
    fetcher = DataFetcher()
    try: brent_df = fetcher.fetch("CL=F", period="1y")
    except: brent_df = None
    return fred.get_macro_context(brent_df)

@st.cache_data(ttl=300)
def analyze_ticker(ticker, _config, _macro_context, category=None):
    if not validate_ticker(ticker): return None
    analyzer = StockAnalyzer(DataFetcher(), DataCleaner(), IndicatorEngine(), ScoringEngine(), _config, _macro_context)
    return analyzer.analyze_ticker(ticker.upper(), category=category)

def load_watchlist_categories():
    """Parse list.txt into categories."""
    categories = {
        "FAVORITES": ["NVDA", "BTC-USD", "BBCA.JK", "GC=F", "TSLA", "TLKM.JK"]
    }
    list_path = Path(__file__).parent / "list.txt"
    if list_path.exists():
        current_cat = "OTHERS"
        with open(list_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.endswith(":"):
                    current_cat = line[:-1].upper()
                    if current_cat not in categories:
                        categories[current_cat] = []
                else:
                    ticker = line.upper()
                    if current_cat not in categories:
                        categories[current_cat] = []
                    if ticker not in categories[current_cat]:
                        categories[current_cat].append(ticker)
    return categories

from concurrent.futures import ThreadPoolExecutor, as_completed


def run_parallel_scan(unique_tickers, config, macro_context, category, status_container):
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_ticker = {
            executor.submit(analyze_ticker, norm_t, config, macro_context, category=category): norm_t
            for raw_t, norm_t in unique_tickers
        }
        for future in as_completed(future_to_ticker):
            norm_t = future_to_ticker[future]
            try:
                res = future.result()
                if res:
                    results.append({
                        "TICKER": res.ticker,
                        "SIG": res.signal.value,
                        "CSS": round(res.css, 1),
                        "ML": res.ml_signal,
                        "PRICE": f"{res.current_price:,.2f}",
                        "SCORE": round(res.score, 1),
                        "1W_FC": f"{res.forecast_1w*100:+.1f}%",
                        "1M_FC": f"{res.forecast_1m*100:+.1f}%"
                    })
                status_container.write(f"DONE: {norm_t}")
            except Exception as e:
                status_container.error(f"FAILED: {norm_t} - {e}")
    return results

def main():
    config = AppConfig.load()

    if not check_security(config):
        return

    # Sidebar - Minimalist
    st.sidebar.title("ZHVNY_CORE")

    # --- AUTO REFRESH LOGIC ---
    if st.sidebar.checkbox("AUTO_REFRESH (5M)", value=True):
        components.html(
            """
            <script>
                setTimeout(function() {
                    window.parent.location.reload();
                }, 300000);
            </script>
            """,
            height=0,
        )

    with st.sidebar:
        with st.spinner("FETCHING_MACRO..."):
            macro_context = get_macro_context(config)
        st.markdown(f"**REGIME:** `{macro_context['regime']}`")
        st.sidebar.markdown(f"**LIQ_PULSE:** `{macro_context['lpi']:.2f}`")

    menu = ["DASHBOARD", "ANALYSIS", "MACRO", "PORTFOLIO"]
    choice = st.sidebar.radio("", menu)

    st.sidebar.divider()

    # Watchlist Category Selector
    watchlist_cats = load_watchlist_categories()
    st.sidebar.subheader("WATCHLIST")
    cat_choice = st.sidebar.selectbox("CATEGORY", list(watchlist_cats.keys()))

    if st.sidebar.button("CLEAR_CACHE"):
        st.cache_data.clear()
        st.rerun()

    if choice == "DASHBOARD":
        st.subheader("SYSTEM_OVERVIEW")

        # Grid metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("REGIME", macro_context['regime'])
        m2.metric("LPI", f"{macro_context['lpi']:.2f}")
        m3.metric("YCMO", f"{macro_context.get('ycmo', 0):.2f}")
        m4.metric("ICM", f"{macro_context.get('icm', 0):.2f}")

        st.divider()

        # Load categories
        watchlist_cats = load_watchlist_categories()

        # Create Tabs for clear separation
        tab_us, tab_idx, tab_others = st.tabs(["🇺🇸 US_MARKET", "🇮🇩 IDX_MARKET", "🌐 OTHER_ASSETS"])

        with tab_us:
            tickers = watchlist_cats.get("US STOCKS", [])
            if tickers:
                # Centralized normalization & deduplication
                fetcher = DataFetcher()
                seen = set()
                unique_tickers = []
                for t in tickers:
                    norm = fetcher.normalize(t, "US")
                    if norm not in seen:
                        unique_tickers.append((t, norm))
                        seen.add(norm)

                with st.status("SCANNING_WALL_STREET...", expanded=False) as status:
                    results = run_parallel_scan(unique_tickers, config, macro_context, "US", status)
                    status.update(label="US_SCAN_COMPLETE", state="complete")

                if results:
                    st.table(pd.DataFrame(results).sort_values(by="CSS", ascending=False))
            else:
                st.info("NO_US_STOCKS_FOUND")

        with tab_idx:
            tickers = watchlist_cats.get("IDX STOCKS", [])
            if tickers:
                fetcher = DataFetcher()
                seen = set()
                unique_tickers = []
                for t in tickers:
                    norm = fetcher.normalize(t, "IDX")
                    if norm not in seen:
                        unique_tickers.append((t, norm))
                        seen.add(norm)

                with st.status("SCANNING_IDX_BURSA...", expanded=False) as status:
                    results = run_parallel_scan(unique_tickers, config, macro_context, "IDX", status)
                    status.update(label="IDX_SCAN_COMPLETE", state="complete")

                if results:
                    st.table(pd.DataFrame(results).sort_values(by="CSS", ascending=False))
            else:
                st.info("NO_IDX_STOCKS_FOUND")

        with tab_others:
            # Group all other categories here
            other_keys = [k for k in watchlist_cats.keys() if k not in ["US STOCKS", "IDX STOCKS", "FAVORITES"]]
            if other_keys:
                sub_cat = st.selectbox("SELECT_CATEGORY", other_keys)
                tickers = watchlist_cats.get(sub_cat, [])
                fetcher = DataFetcher()
                seen = set()
                unique_tickers = []
                for t in tickers:
                    norm = fetcher.normalize(t, sub_cat)
                    if norm not in seen:
                        unique_tickers.append((t, norm))
                        seen.add(norm)

                with st.status(f"SCANNING_{sub_cat}...", expanded=False) as status:
                    results = run_parallel_scan(unique_tickers, config, macro_context, sub_cat, status)
                    status.update(label=f"{sub_cat}_SCAN_COMPLETE", state="complete")

                if results:
                    st.table(pd.DataFrame(results).sort_values(by="CSS", ascending=False))


    elif choice == "ANALYSIS":
        st.subheader("DEEP_SCAN")
        t_input = st.text_input("TICKER_ID", "BBCA.JK").upper().strip()

        if t_input:
            if not validate_ticker(t_input):
                st.error("INVALID_INPUT_PATTERN")
            else:
                with st.spinner(f"EXTRACTING_VECTORS: {t_input}..."):
                    res = analyze_ticker(t_input, config, macro_context)

                if res:
                    c1, c2, c3 = st.columns([1,1,2])
                    with c1:
                        st.metric("PRICE", f"{res.current_price:,.2f}")
                        st.markdown(f"**SIGNAL:** `{res.signal.value}`")
                    with c2:
                        st.metric("CSS", f"{res.css:.1f}")
                        st.metric("ML_PROB", f"{res.ml_prob:.3f}")

                    with c3:
                        st.markdown("**STRATEGY**")
                        st.text(f"SL: {res.stop_loss:,.2f} | TP: {res.take_profit:,.2f}")
                        st.text(f"SR: {res.support:,.2f} / {res.resistance:,.2f}")

                    # Minimalist Plotly
                    with st.spinner("GENERATING_VIZ..."):
                        fetcher = DataFetcher()
                        hist = fetcher.fetch(t_input, period="1y")
                        if not hist.empty:
                            fig = go.Figure(data=[go.Scatter(x=hist.index, y=hist['Close'], line=dict(color='#00ff00', width=1))])
                            fig.update_layout(
                                template="plotly_dark", height=300, margin=dict(l=0, r=0, t=0, b=0),
                                paper_bgcolor="black", plot_bgcolor="black",
                                xaxis=dict(showgrid=False), yaxis=dict(showgrid=False)
                            )
                            st.plotly_chart(fig, use_container_width=True)

    elif choice == "MACRO":
        st.subheader("GLOBAL_VECTORS")
        fred = FREDFetcher(config)
        fred_data = fred.fetch_all()
        if fred_data:
            st.table(pd.DataFrame(fred_data)[['name', 'value', 'change', 'influence']])

    elif choice == "PORTFOLIO":
        st.subheader("ACTIVE_POSITIONS")
        pm = PortfolioManager()
        positions = pm.load_positions()
        if positions:
            p_res = []
            for p in positions:
                r = analyze_ticker(p['ticker'], config, macro_context)
                if r:
                    p_res.append({
                        "TICKER": p['ticker'],
                        "SIG": r.signal.value,
                        "PRICE": r.current_price,
                        "ENTRY": p['entry'],
                        "PL_PCT": f"{((r.current_price - p['entry'])/p['entry'])*100:+.2f}%" if p['entry'] else "0%",
                        "CSS": r.css
                    })
            st.table(pd.DataFrame(p_res))
        else:
            st.info("PORTFOLIO_EMPTY")

    # Status Bar
    st.markdown(f'<div class="status-bar">SYSTEM_READY | {datetime.now().strftime("%H:%M:%S")} | {macro_context["regime"]} | AUTH_OK</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
