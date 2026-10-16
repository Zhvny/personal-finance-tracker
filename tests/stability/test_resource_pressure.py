import pytest

pytestmark = pytest.mark.xfail(
    reason="Stability tests need real backend; tracked separately (tracking: gate-split)", strict=False
)
import json
import logging
import os
import time

import psutil
import requests
import urllib3

# Suppress insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# SECURITY: verify default True; self-signed lokal via CA_BUNDLE env.
_VERIFY = os.environ.get("CA_BUNDLE", True)

# Configuration
API_PID = 27384
BASE_URL = "https://localhost:8444/api/ticker"
TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NFLX", "META", "NVDA", "PYPL", "INTC"] * 5  # 50 switches
DELAY = 0.2
LOG_FILE = r"../../logs/stress_test.log"
LEAK_FILE = r"../../logs/leak_analysis.json"

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_process_stats(pid):
    try:
        proc = psutil.Process(pid)
        return {"memory_rss_mb": proc.memory_info().rss / (1024 * 1024), "cpu_percent": proc.cpu_percent(interval=0.1)}
    except Exception as e:
        logging.error(f"Error getting stats for PID {pid}: {e}")
        return None


def run_stress_test():
    stats_history = []
    failures = 0

    # Baseline
    baseline = get_process_stats(API_PID)
    logging.info(f"Baseline Stats: {baseline}")

    print(f"Starting 50 switches on PID {API_PID}...")

    for i, ticker in enumerate(TICKERS):
        try:
            # Main endpoint
            start_time = time.time()
            res = requests.get(f"{BASE_URL}/{ticker}/base", verify=_VERIFY, timeout=5)
            latency = time.time() - start_time

            if res.status_code != 200:
                logging.error(f"Switch {i+1} ({ticker}) failed with status {res.status_code}")
                failures += 1
            else:
                logging.info(f"Switch {i+1} ({ticker}) - Latency: {latency:.4f}s")

            # Simulate analytical endpoint call often paired in GUI
            requests.get(f"https://localhost:8444/api/behavioral/sentiment/{ticker}", verify=_VERIFY, timeout=5)

        except Exception as e:
            logging.error(f"Switch {i+1} ({ticker}) error: {e}")
            failures += 1

        if (i + 1) % 10 == 0:
            current = get_process_stats(API_PID)
            stats_history.append(current)
            print(f"Progress: {i+1}/50. Current Mem: {current['memory_rss_mb']:.2f} MB")

        time.sleep(DELAY)

    print("Cooling down for 10s for GC...")
    time.sleep(10)

    final = get_process_stats(API_PID)
    logging.info(f"Final Stats: {final}")

    leak_data = {
        "baseline": baseline,
        "final": final,
        "delta_mb": final["memory_rss_mb"] - baseline["memory_rss_mb"] if baseline and final else None,
        "total_requests": len(TICKERS),
        "failures": failures,
        "leak_detected": (final["memory_rss_mb"] - baseline["memory_rss_mb"]) > 5.0 if baseline and final else False,
    }

    with open(LEAK_FILE, "w") as f:
        json.dump(leak_data, f, indent=4)

    print(f"Test Complete. Failures: {failures}. Leak Data saved to {LEAK_FILE}")


if __name__ == "__main__":
    run_stress_test()
