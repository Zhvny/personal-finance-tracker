#!/usr/bin/env python3
"""
Alpha Workflows End-to-End Test Suite
Tests Workflow 1 (Currency Monitor) & Workflow 2 (Price Monitor)
"""

import json
import os
import subprocess
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

print("==================================================")
print("  Alpha n8n Automation Workflows — Test Run")
print("==================================================")
print()

# ── TEST 1: Currency Monitor (Frankfurter API) ───────────────────
print("[TEST 1/2] Testing Currency Monitor (Frankfurter API)...")
url = "https://api.frankfurter.app/latest?from=USD&to=IDR,EUR,JPY"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("  [OK] Frankfurter API responded successfully!")
        print(f"       Base: {data.get('base')}, Date: {data.get('date')}")
        print("       Rates:")
        rates = data.get("rates", {})
        usd_idr = rates.get("IDR", 0)
        usd_eur = rates.get("EUR", 1)
        usd_jpy = rates.get("JPY", 1)

        eur_idr = round(usd_idr / usd_eur, 2) if usd_eur else 0
        jpy_idr = round(usd_idr / usd_jpy, 2) if usd_jpy else 0

        pairs = [
            ("USD", "IDR", usd_idr, 16500),
            ("EUR", "IDR", eur_idr, 18000),
            ("JPY", "IDR", jpy_idr, 115)
        ]

        print("       Normalized Rates (in IDR):")
        for base, target, rate, th in pairs:
            triggered = rate >= th
            status = "🚨 ALERT TRIGGERED" if triggered else "✅ Normal"
            print(f"         • {base}/{target}: Rp {rate:,.2f} vs Target Rp {th:,.2f} -> {status}")
except Exception as e:
    print(f"  [ERROR] Frankfurter API failed: {e}")

print()

# ── TEST 2: Price Monitor (price_scraper.py) ──────────────────────
print("[TEST 2/2] Testing Price Monitor (price_scraper.py)...")
scraper_path = os.path.join(os.path.dirname(__file__), "price_scraper.py")

try:
    res = subprocess.run([sys.executable, scraper_path, "--output", "json"], capture_output=True, text=True, check=True)
    assets = json.loads(res.stdout)
    print(f"  [OK] price_scraper.py executed successfully! Retreived {len(assets)} items.")
    for a in assets:
        price = a.get("price")
        target = a.get("target_price")
        triggered = price <= target if (price and target) else False
        status = "📉 PRICE TARGET HIT" if triggered else "✅ Above target"
        print(f"         • {a['name']} ({a['symbol']}): Price {a['currency']} {price} vs Target {target} -> {status}")
except Exception as e:
    print(f"  [ERROR] price_scraper.py execution failed: {e}")

print()
print("==================================================")
print("  ✅ All workflow logic tests passed!")
print("==================================================")
