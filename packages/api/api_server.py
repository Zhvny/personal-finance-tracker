#!/usr/bin/env python3
"""
Finance Tracker — GUI API Bridge (Alpha Microservice Wrapper)
=============================================================
Re-exports the canonical Alpha Microservice app from `apps.api.main`.
Maintains backwards compatibility for legacy invocation scripts.
"""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from apps.api.main import app, create_app  # noqa: E402,F401 (bridge re-export)


if __name__ == "__main__":
    import uvicorn

    from apps.api.config import settings

    host = settings.HOST
    port = settings.PORT

    use_https = settings.SSL_CERT_PATH.exists() and settings.SSL_KEY_PATH.exists()
    protocol = "https" if use_https else "http"

    print(f"\n[*] Launching Alpha Microservice via Bridge Wrapper on {host}:{port} ({protocol.upper()})")

    if use_https:
        uvicorn.run(
            "apps.api.main:app",
            host=host,
            port=port,
            reload=False,
            ssl_keyfile=str(settings.SSL_KEY_PATH),
            ssl_certfile=str(settings.SSL_CERT_PATH),
            log_level="info"
        )
    else:
        uvicorn.run("apps.api.main:app", host=host, port=port, reload=False, log_level="info")
