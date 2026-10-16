"""alpha-engagement :8455 — behavioral finance (FBS) and reward economy."""

from services.runtime.bootstrap import create_service_app, run_service

ROUTERS = [
    "behavioral",
    "rewards",
]

app = create_service_app(
    service_name="alpha-engagement",
    default_port=8455,
    routers=ROUTERS,
)

if __name__ == "__main__":
    run_service(app, "alpha-engagement")
