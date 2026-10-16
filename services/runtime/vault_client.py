from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("alpha.vault")

_K8S_SA_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"


def _vault_addr() -> str:
    return os.getenv("VAULT_ADDR", "")


def _headers() -> dict[str, str]:
    addr = _vault_addr()
    if not addr:
        raise RuntimeError("vault unavailable")
    try:
        with open(_K8S_SA_TOKEN_PATH) as f:
            token = f.read().strip()
        return {"X-Vault-Token": token}
    except Exception as e:
        raise RuntimeError("vault unavailable") from e


def get_secret(path: str) -> dict[str, Any]:
    addr = _vault_addr()
    if not addr:
        raise RuntimeError("vault unavailable")
    try:
        resp = httpx.get(f"{addr}/v1/{path}", headers=_headers(), timeout=3)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {})
    except RuntimeError:
        raise
    except Exception as e:
        logger.warning(f"vault read {path} failed: {e}")
        raise RuntimeError("vault unavailable") from e
