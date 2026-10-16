"""
backend/routers/logs.py — Datadog Log Cockpit API Routes
=========================================================
Exposes microservice endpoints for reading live log streams, calculating Datadog observability metrics, and exporting logs.
"""

import datetime
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query

from packages.api.backend.security.core import require_scope

router = APIRouter(prefix="/api/logs", tags=["Datadog Logs"], dependencies=[Depends(require_scope("read"))])

_PROJECT_ROOT = Path(__file__).resolve().parents[4]

LOG_SOURCES = {
    "microservice": {
        "name": "Alpha Microservice API",
        "badge": "MICROSERVICE",
        "color": "#38bdf8",
        "path": _PROJECT_ROOT / "apps" / "api" / "alpha_microservice.log"
    },
    "cli": {
        "name": "CLI & Schedulers",
        "badge": "CLI",
        "color": "#c084fc",
        "path": _PROJECT_ROOT / "logs" / "app.log"
    },
    "api": {
        "name": "API Boot & Gateway",
        "badge": "API",
        "color": "#f472b6",
        "path": _PROJECT_ROOT / "logs" / "api_server_boot.log"
    },
    "optimizer": {
        "name": "Genetic Optimizer",
        "badge": "OPTIMIZER",
        "color": "#fbbf24",
        "path": _PROJECT_ROOT / "logs" / "optimizer_exclusions.log"
    },
    "security": {
        "name": "Security Audit Log",
        "badge": "SECURITY",
        "color": "#f87171",
        "path": _PROJECT_ROOT / "logs" / "security_audit.log"
    },
    "dr_backup": {
        "name": "Disaster Recovery",
        "badge": "RECOVERY",
        "color": "#34d399",
        "path": _PROJECT_ROOT / "logs" / "dr_backup.log"
    },
}

TIMESTAMP_REGEX = re.compile(
    r'(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)'
)


def classify_line(line: str) -> str:
    line_upper = line.upper()
    for level in ("CRITICAL", "ERROR", "WARNING", "WARN", "INFO", "DEBUG"):
        if level in line_upper:
            if level == "WARN":
                return "WARNING"
            return level
    return "INFO"


def extract_ts(line: str) -> str:
    match = TIMESTAMP_REGEX.search(line)
    if match:
        return match.group(1).replace("T", " ")[:19]
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@router.get("/sources")
def get_log_sources():
    """List available Datadog log sources and file statuses."""
    result = []
    for key, info in LOG_SOURCES.items():
        path: Path = info["path"]
        exists = path.exists()
        size_bytes = path.stat().st_size if exists else 0
        result.append({
            "key": key,
            "name": info["name"],
            "badge": info["badge"],
            "color": info["color"],
            "exists": exists,
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "filename": path.name
        })
    return {"sources": result}


@router.get("/stream")
def get_log_stream(
    service: Optional[str] = Query(None, description="Filter by service key (e.g. microservice, cli)"),
    level: Optional[str] = Query("ALL", description="Filter by log level (ALL, INFO, WARNING, ERROR, CRITICAL)"),
    search: Optional[str] = Query(None, description="Search query string"),
    limit: int = Query(200, ge=1, le=2000, description="Max entries to return")
):
    """Get interleaved chronological log entries across services."""
    entries = []
    target_sources = [service] if service and service in LOG_SOURCES else list(LOG_SOURCES.keys())

    for key in target_sources:
        path = LOG_SOURCES[key]["path"]
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            for line in lines[-500:]:
                s = line.strip()
                if not s:
                    continue
                lv = classify_line(s)

                if level and level != "ALL":
                    if level == "ERROR" and lv not in ("ERROR", "CRITICAL"):
                        continue
                    elif level != "ERROR" and lv != level:
                        continue

                if search and search.lower() not in s.lower():
                    continue

                ts = extract_ts(s)
                entries.append({
                    "timestamp": ts,
                    "service": key,
                    "service_badge": LOG_SOURCES[key]["badge"],
                    "service_color": LOG_SOURCES[key]["color"],
                    "level": lv,
                    "message": s
                })
        except Exception:
            pass

    # Sort chronologically by timestamp
    entries.sort(key=lambda x: x["timestamp"])
    return {
        "total_returned": len(entries[-limit:]),
        "entries": entries[-limit:]
    }


@router.get("/stats")
def get_log_stats():
    """Get Datadog observability summary metrics (ingestion volume, error rates, source health)."""
    total_lines = 0
    total_bytes = 0
    info_cnt = warn_cnt = err_cnt = 0
    source_stats = []

    for key, info in LOG_SOURCES.items():
        path = info["path"]
        if not path.exists():
            source_stats.append({
                "service": key,
                "name": info["name"],
                "badge": info["badge"],
                "lines": 0,
                "errors": 0,
                "status": "OFFLINE"
            })
            continue

        try:
            size = path.stat().st_size
            total_bytes += size
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            lines_cnt = len(lines)
            total_lines += lines_cnt

            s_info = s_warn = s_err = 0
            for line in lines:
                lv = classify_line(line)
                if lv in ("ERROR", "CRITICAL"):
                    s_err += 1
                elif lv == "WARNING":
                    s_warn += 1
                else:
                    s_info += 1

            info_cnt += s_info
            warn_cnt += s_warn
            err_cnt += s_err

            source_stats.append({
                "service": key,
                "name": info["name"],
                "badge": info["badge"],
                "lines": lines_cnt,
                "info": s_info,
                "warn": s_warn,
                "errors": s_err,
                "status": "HEALTHY" if s_err == 0 else "ATTENTION"
            })
        except Exception:
            pass

    err_rate = round((err_cnt / total_lines * 100), 2) if total_lines > 0 else 0.0

    return {
        "total_lines": total_lines,
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "info_count": info_cnt,
        "warn_count": warn_cnt,
        "error_count": err_cnt,
        "error_rate_pct": err_rate,
        "sources": source_stats
    }
