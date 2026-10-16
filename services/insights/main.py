"""alpha-insights :8454 — OCR receipts, merchant map, AI advisor, analytics,
anomalies, health score.

honey: analytics.py spans ledger/portfolio/platform segments
(/api/logs/recent, /api/analytics/*); parked whole here until split.
"""

from services.runtime.bootstrap import create_service_app, run_service

ROUTERS = [
    "receipts",
    "merchant",
    "ai",
    "insights",
    "analytics",
    "anomalies",
    "health_score",
]

app = create_service_app(
    service_name="alpha-insights",
    default_port=8454,
    routers=ROUTERS,
)

if __name__ == "__main__":
    run_service(app, "alpha-insights")
