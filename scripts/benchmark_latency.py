import json
import os
import time
from datetime import datetime
from pathlib import Path

import psutil
import requests

# Setup paths
PROJECT_ROOT = Path(".")
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = LOG_DIR / "benchmark_latency_baseline.json"

# API Configuration
HOST = "127.0.0.1"
PORT = 8444
BASE_URL = f"https://{HOST}:{PORT}/api"
TEST_TICKER = "BBCA.JK"

# Endpoints to benchmark
ENDPOINTS = [
    {"name": "ticker_base", "url": f"{BASE_URL}/stocks/analyze/{TEST_TICKER}/base"},
    {"name": "ticker_chart", "url": f"{BASE_URL}/stocks/analyze/{TEST_TICKER}/chart?period=1y"},
    {"name": "ticker_technicals", "url": f"{BASE_URL}/stocks/analyze/{TEST_TICKER}/technicals"},
    {"name": "ticker_sentiment", "url": f"{BASE_URL}/stocks/analyze/{TEST_TICKER}/sentiment"},
    {"name": "ticker_dxy", "url": f"{BASE_URL}/stocks/analyze/{TEST_TICKER}/dxy"},
    {"name": "ticker_butterfly", "url": f"{BASE_URL}/butterfly/risk-map/{TEST_TICKER}"},
    {"name": "ticker_senate", "url": f"{BASE_URL}/senate/{TEST_TICKER}"},
]

def find_api_process():
    """Find the api_server.py process."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and 'api_server.py' in str(cmdline):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None

def benchmark():
    print(f"Starting API Latency Benchmark for {TEST_TICKER}...")
    api_proc = find_api_process()
    if not api_proc:
        print("Warning: api_server.py process not found. Resource usage will not be tracked.")

    results = {
        "timestamp": datetime.now().isoformat(),
        "ticker": TEST_TICKER,
        "endpoints": [],
        "system_metrics": {}
    }

    if api_proc:
        results["system_metrics"] = {
            "pid": api_proc.pid,
            "cpu_percent": api_proc.cpu_percent(interval=0.1),
            "memory_rss_mb": api_proc.memory_info().rss / (1024 * 1024)
        }

    for ep in ENDPOINTS:
        print(f"  Benchmarking {ep['name']}...")
        try:
            start_time = time.time()
            # Note: headers might be needed if there is auth, but api_server.py says simplified mode
            # SECURITY: verify=True default; self-signed lokal via CA_BUNDLE env.
            response = requests.get(ep["url"], timeout=30, verify=os.environ.get("CA_BUNDLE", True))
            end_time = time.time()

            latency = (end_time - start_time) * 1000  # ms

            ep_result = {
                "name": ep['name'],
                "url": ep['url'],
                "status_code": response.status_code,
                "latency_ms": latency,
                "response_size_kb": len(response.content) / 1024
            }

            if response.status_code != 200:
                print(f"    Error: {ep['name']} returned status {response.status_code}")
                ep_result["error"] = response.text[:200]

        except Exception as e:
            print(f"    Exception: {ep['name']} failed: {str(e)}")
            ep_result = {
                "name": ep['name'],
                "url": ep['url'],
                "status_code": 0,
                "latency_ms": -1,
                "error": str(e)
            }

        results["endpoints"].append(ep_result)

    # Post-benchmark resource usage
    if api_proc:
        results["system_metrics"]["cpu_percent_post"] = api_proc.cpu_percent(interval=0.1)
        results["system_metrics"]["memory_rss_mb_post"] = api_proc.memory_info().rss / (1024 * 1024)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=4)

    print(f"Benchmark complete. Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    benchmark()
