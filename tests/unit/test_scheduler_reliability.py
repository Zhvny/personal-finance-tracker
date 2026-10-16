import subprocess
import time
from unittest.mock import MagicMock, patch

import pytest

from packages.api.backend.automation.market_scheduler import MarketScheduler
from packages.api.backend.automation.scheduler import (
    PID_FILE,
    _acquire_pid_lock,
    _job_status,
    _release_pid_lock,
    _wrap_job,
    job_stock_ml_update,
)


def test_market_scheduler_max_instances_configured():
    scheduler = MarketScheduler()
    scheduler.scheduler = MagicMock()

    scheduler.start()

    calls = scheduler.scheduler.add_job.call_args_list
    assert len(calls) > 0
    for call in calls:
        kwargs = call[1]
        assert "max_instances" in kwargs
        assert kwargs["max_instances"] == 1

def test_wrap_job_success_resets_consecutive_failures():
    job_name = "networth_snapshot"
    _job_status[job_name]["consecutive_failures"] = 5
    _job_status[job_name]["error_count"] = 5

    def success_job():
        pass

    wrapped = _wrap_job(job_name, success_job)
    wrapped()

    assert _job_status[job_name]["consecutive_failures"] == 0
    assert _job_status[job_name]["error_count"] == 5 # Shouldn't reset error_count
    assert _job_status[job_name]["last_status"] == "ok"

def test_wrap_job_failure_increments_error_count():
    job_name = "portfolio_prices"
    initial_errors = _job_status[job_name]["error_count"]
    initial_consecutive = _job_status[job_name]["consecutive_failures"]

    def failing_job():
        raise ValueError("Simulated failure")

    wrapped = _wrap_job(job_name, failing_job)
    wrapped()

    assert _job_status[job_name]["error_count"] == initial_errors + 1
    assert _job_status[job_name]["consecutive_failures"] == initial_consecutive + 1
    assert "error" in _job_status[job_name]["last_status"]

def test_wrap_job_tracks_duration():
    job_name = "behavioral_score"
    _job_status[job_name]["last_duration_s"] = 0.0

    def slow_job():
        time.sleep(0.1)

    wrapped = _wrap_job(job_name, slow_job)
    wrapped()

    assert _job_status[job_name]["last_duration_s"] >= 0.1

def test_stock_ml_job_timeout():
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=300)

        with pytest.raises(subprocess.TimeoutExpired):
            job_stock_ml_update()

def test_scheduler_health_returns_required_fields():
    scheduler = MarketScheduler()
    health = scheduler.get_health()

    for job_name, status in health.items():
        assert "last_run" in status
        assert "last_status" in status
        assert "last_duration_s" in status
        assert "error_count" in status
        assert "consecutive_failures" in status

def test_pid_guard_prevents_double_start():
    # Write current PID to lock file
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        pass

    # First acquire should succeed
    assert _acquire_pid_lock() == True

    # Second acquire should fail because the PID matches a running process (ourselves)
    assert _acquire_pid_lock() == False

    _release_pid_lock()

    # After release, acquire should succeed
    assert _acquire_pid_lock() == True
    _release_pid_lock()

def test_job_status_has_required_fields():
    for job_name, status in _job_status.items():
        assert "last_run" in status
        assert "last_status" in status
        assert "last_duration_s" in status
        assert "error_count" in status
        assert "consecutive_failures" in status
        assert "next_run_after" in status
