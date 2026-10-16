#!/usr/bin/env python3
"""
Alpha Price Scraper - price_scraper.py
=======================================
Scraper untuk Stocks, Crypto, dan Komoditas.
Dijalankan oleh n8n Execute Command node.

Output: JSON array ke stdout
Usage:  python3 price_scraper.py --output json

Dependencies:
    pip install requests playwright python-dotenv
    playwright install chromium
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from typing import Optional

# ── Optional: Load .env for local dev ────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
log = logging.getLogger("alpha.scraper")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG: Define your watchlist here
# target_price = harga yang ingin kamu beli / alert threshold
# ─────────────────────────────────────────────────────────────────────────────
WATCHLIST = [
    # === CRYPTO ===
    {
        "symbol": "BTC",
        "name": "Bitcoin",
        "type": "crypto",
        "currency": "USD",
        "target_price": 55000.0,
        "coingecko_id": "bitcoin",
    },
    {
        "symbol": "ETH",
        "name": "Ethereum",
        "type": "crypto",
        "currency": "USD",
        "target_price": 2800.0,
        "coingecko_id": "ethereum",
    },
    {
        "symbol": "SOL",
        "name": "Solana",
        "type": "crypto",
        "currency": "USD",
        "target_price": 120.0,
        "coingecko_id": "solana",
    },
    # === STOCKS (Yahoo Finance) ===
    {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "type": "stocks",
        "currency": "USD",
        "target_price": 190.0,
        "yahoo_ticker": "AAPL",
    },
    {
        "symbol": "BBRI",
        "name": "Bank BRI",
        "type": "stocks",
        "currency": "IDR",
        "target_price": 4000.0,
        "yahoo_ticker": "BBRI.JK",
    },
    # === COMMODITIES ===
    {
        "symbol": "GOLD",
        "name": "Gold (XAU/USD)",
        "type": "commodity",
        "currency": "USD",
        "target_price": 2300.0,
        "yahoo_ticker": "GC=F",
    },
    {
        "symbol": "OIL",
        "name": "Crude Oil (WTI)",
        "type": "commodity",
        "currency": "USD",
        "target_price": 70.0,
        "yahoo_ticker": "CL=F",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# FETCHERS
# ─────────────────────────────────────────────────────────────────────────────

def fetch_crypto_prices(assets: list) -> dict:
    """Fetch crypto prices from CoinGecko free API."""
    import requests

    ids = ",".join(a["coingecko_id"] for a in assets if "coingecko_id" in a)
    if not ids:
        return {}

    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": ids, "vs_currencies": "usd"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error(f"CoinGecko error: {e}")
        return {}


def fetch_yahoo_price(ticker: str) -> Optional[float]:
    """
    Fetch latest price from Yahoo Finance unofficial API.
    Falls back to Playwright scraping if API fails.
    """
    import requests

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        price = (
            data.get("chart", {})
            .get("result", [{}])[0]
            .get("meta", {})
            .get("regularMarketPrice")
        )
        return float(price) if price is not None else None
    except Exception as e:
        log.warning(f"Yahoo API failed for {ticker}: {e}. Trying Playwright...")
        return fetch_yahoo_playwright(ticker)


def fetch_yahoo_playwright(ticker: str) -> Optional[float]:
    """Fallback: scrape Yahoo Finance with Playwright (headless)."""
    try:
        from playwright.sync_api import sync_playwright

        url = f"https://finance.yahoo.com/quote/{ticker}/"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)
            # Try multiple selectors
            selectors = [
                'fin-streamer[data-field="regularMarketPrice"]',
                '[data-testid="qsp-price"]',
                '.Fw\\(b\\).Fz\\(36px\\)',
            ]
            price_text = None
            for sel in selectors:
                try:
                    el = page.query_selector(sel)
                    if el:
                        price_text = el.get_attribute("value") or el.inner_text()
                        break
                except Exception:
                    continue
            browser.close()

        if price_text:
            clean = price_text.replace(",", "").strip()
            return float(clean)
    except Exception as e:
        log.error(f"Playwright fallback failed for {ticker}: {e}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_scraper() -> list:
    """Run all scrapers and return unified results list."""
    results = []
    now = datetime.utcnow().isoformat() + "Z"

    # Separate assets by type
    crypto_assets = [a for a in WATCHLIST if a["type"] == "crypto"]
    market_assets = [a for a in WATCHLIST if a["type"] in ("stocks", "commodity")]

    # --- CRYPTO ---
    crypto_data = fetch_crypto_prices(crypto_assets)
    for asset in crypto_assets:
        gecko_id = asset.get("coingecko_id", "")
        price_data = crypto_data.get(gecko_id, {})
        price = price_data.get("usd")
        results.append({
            "symbol": asset["symbol"],
            "name": asset["name"],
            "type": asset["type"],
            "price": price,
            "currency": asset["currency"],
            "target_price": asset["target_price"],
            "source": "coingecko",
            "scraped_at": now,
            "error": None if price is not None else "price_not_found",
        })

    # --- STOCKS & COMMODITIES ---
    for asset in market_assets:
        ticker = asset.get("yahoo_ticker", asset["symbol"])
        price = fetch_yahoo_price(ticker)
        results.append({
            "symbol": asset["symbol"],
            "name": asset["name"],
            "type": asset["type"],
            "price": price,
            "currency": asset["currency"],
            "target_price": asset["target_price"],
            "source": "yahoo_finance",
            "scraped_at": now,
            "error": None if price is not None else "price_not_found",
        })

    return results


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Alpha Price Scraper")
    parser.add_argument(
        "--output",
        choices=["json", "pretty"],
        default="json",
        help="Output format (default: json)"
    )
    parser.add_argument(
        "--filter-type",
        choices=["crypto", "stocks", "commodity"],
        default=None,
        help="Filter by asset type"
    )
    args = parser.parse_args()

    data = run_scraper()

    if args.filter_type:
        data = [d for d in data if d["type"] == args.filter_type]

    if args.output == "pretty":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        # Compact JSON for n8n stdout parsing
        print(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()
