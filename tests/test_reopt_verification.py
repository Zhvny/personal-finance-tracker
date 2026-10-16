import json
import logging

# Setup paths for import
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import BackgroundTasks

_GUI_DIR = Path(r"../finance-tracker-gui")
_CLI_DIR = Path(r"../../../Tools/Gemini-Manager/apps/cli")
_ANALYZER_DIR = Path(r"..\apps\stock_analyzer")
_PROJECT_ROOT = Path(r"..")

if str(_GUI_DIR) not in sys.path: sys.path.append(str(_GUI_DIR))
if str(_CLI_DIR) not in sys.path: sys.path.append(str(_CLI_DIR))
if str(_ANALYZER_DIR) not in sys.path: sys.path.append(str(_ANALYZER_DIR))
if str(_PROJECT_ROOT) not in sys.path: sys.path.append(str(_PROJECT_ROOT))

# Mock security and DB dependencies before importing the router
with patch("backend.security.core.require_scope", return_value=lambda x: (lambda: "admin")):
    from backend.routers.genetic import (
        OptimizationRequest,
        execute_optimization_task,
        get_optimization_status,
        run_portfolio_optimization,
    )

# Mock in-memory task store
optimization_tasks = {}

class MockDB:
    @staticmethod
    def execute(query, params=(), schema=None):
        query_upper = query.upper()
        if "INSERT INTO SYSTEM.OPTIMIZATION_TASKS" in query_upper:
            task_id, profile_id, status, progress, input_params = params
            optimization_tasks[task_id] = {
                "task_id": task_id,
                "profile_id": profile_id,
                "status": status,
                "progress": progress,
                "input_params": json.loads(input_params) if isinstance(input_params, str) else input_params,
                "error": None,
                "result": None
            }
        elif "UPDATE SYSTEM.OPTIMIZATION_TASKS" in query_upper:
            task_id = params[-1]
            if task_id not in optimization_tasks:
                return 0
            if "STATUS = %S, ERROR = %S" in query_upper:
                optimization_tasks[task_id]["status"] = params[0]
                optimization_tasks[task_id]["error"] = params[1]
            elif "STATUS = %S, RESULT = %S, PROGRESS = 100" in query_upper:
                optimization_tasks[task_id]["status"] = params[0]
                optimization_tasks[task_id]["result"] = json.loads(params[1]) if isinstance(params[1], str) else params[1]
                optimization_tasks[task_id]["progress"] = 100
            elif "STATUS = %S" in query_upper:
                optimization_tasks[task_id]["status"] = params[0]
            elif "PROGRESS = %S" in query_upper:
                optimization_tasks[task_id]["progress"] = params[0]
        return 1

    @staticmethod
    def query(query, params=(), schema=None):
        query_upper = query.upper()
        if "SELECT * FROM SYSTEM.OPTIMIZATION_TASKS" in query_upper:
            task_id = params[0]
            if task_id in optimization_tasks:
                # Return as list of dicts to match DatabaseManager.query
                return [optimization_tasks[task_id]]
        return []

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.fixture
def mock_background_tasks():
    return MagicMock(spec=BackgroundTasks)

@pytest.fixture(autouse=True)
def mock_db_manager():
    with patch("backend.routers.genetic.DatabaseManager", new=MockDB):
        optimization_tasks.clear()
        yield MockDB

@pytest.mark.anyio
async def test_optimize_trigger_accepted(mock_background_tasks):
    """REQ-3: Verify 202 Accepted status and task ID generation with polling."""
    request = OptimizationRequest(tickers=["AAPL", "MSFT"], risk_mode="sharpe")

    # Mock profile service
    with patch("backend.routers.genetic._profile_service.get_active_profile", return_value="personal"):
        response = await run_portfolio_optimization(request, mock_background_tasks)

    assert response["status"] == "accepted"
    assert "task_id" in response
    task_id = response["task_id"]
    mock_background_tasks.add_task.assert_called_once()

    # Verify initial status via status endpoint
    status_resp = await get_optimization_status(task_id)
    assert status_resp["status"] == "pending"
    assert status_resp["task_id"] == task_id

    # Poll status until terminal state
    terminal_states = ["completed", "failed", "timeout"]
    status = "pending"

    # We simulate a polling loop. In a real e2e test, the background task would be running.
    # Here we manually advance state to verify the polling response parsing.
    for i in range(5):
        status_resp = await get_optimization_status(task_id)
        status = status_resp["status"]

        if status in terminal_states:
            break

        if status == "pending":
            # Simulate background task moving to processing
            MockDB.execute("UPDATE system.optimization_tasks SET status = %s WHERE task_id = %s", ("processing", task_id))
        elif status == "processing":
            # Simulate background task completion
            MockDB.execute(
                "UPDATE system.optimization_tasks SET status = %s, result = %s, progress = 100 WHERE task_id = %s",
                ("completed", json.dumps({"weights": {"AAPL": 0.6, "MSFT": 0.4}}), task_id)
            )

    assert status == "completed"
    assert status_resp["progress"] == 100
    assert "AAPL" in status_resp["result"]["weights"]

@pytest.mark.anyio
async def test_optimize_and_poll_failure(mock_background_tasks):
    """Verify that failure results in actionable error message in status response."""
    request = OptimizationRequest(tickers=["INVALID"], risk_mode="sharpe")

    with patch("backend.routers.genetic._profile_service.get_active_profile", return_value="personal"):
        response = await run_portfolio_optimization(request, mock_background_tasks)

    task_id = response["task_id"]

    # Simulate background task failure
    error_msg = "No data found in Postgres for requested tickers."
    MockDB.execute(
        "UPDATE system.optimization_tasks SET status = %s, error = %s WHERE task_id = %s",
        ("failed", error_msg, task_id)
    )

    # Verify failure status and actionable error via status endpoint
    status_resp = await get_optimization_status(task_id)
    assert status_resp["status"] == "failed"
    assert status_resp["error"] == error_msg
    assert "No data found" in status_resp["error"]

@pytest.mark.anyio
async def test_optimize_invalid_tickers_logic(mock_background_tasks):
    """REQ-2: Verify handling of non-existent/invalid tickers."""
    request = OptimizationRequest(tickers=[], risk_mode="sharpe")

    with patch("backend.repositories.stock_repository.StockRepository.get_favorites", return_value=[]):
        with patch("backend.routers.genetic._profile_service.get_active_profile", return_value="personal"):
            response = await run_portfolio_optimization(request, mock_background_tasks)

    task_id = response["task_id"]
    status_resp = await get_optimization_status(task_id)

    # Fallback list should be used by the time execute_optimization_task is called
    mock_background_tasks.add_task.assert_called_once()
    args = mock_background_tasks.add_task.call_args[0]
    # args[2] is the 'tickers' list passed to the task
    # Verify that the emergency fallback tickers are being used (subset check)
    EMERGENCY_FALLBACK = {"AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"}
    used_tickers = set(args[2])
    assert len(used_tickers) > 0, "No tickers passed to background task — fallback failed"
    assert used_tickers.issubset(EMERGENCY_FALLBACK), (
        f"Unexpected tickers used: {used_tickers - EMERGENCY_FALLBACK}. "
        f"Expected a subset of the emergency fallback: {EMERGENCY_FALLBACK}"
    )

@pytest.mark.anyio
async def test_optimization_task_flow_failure_no_data(caplog):
    """REQ-4: Verify log trace completeness and failure status."""
    task_id = str(uuid.uuid4())
    # Pre-insert task
    MockDB.execute(
        "INSERT INTO system.optimization_tasks (task_id, profile_id, status, progress, input_params) VALUES (%s, %s, %s, %s, %s)",
        (task_id, "test-profile", "pending", 0, "{}")
    )

    request = OptimizationRequest(tickers=["INVALID_TKR"])

    with caplog.at_level(logging.INFO, logger="api.genetic_optimizer"):
        with patch("packages.core.infrastructure.persistence.postgres_ohlcv_repository.PostgresOHLCVRepository.get", return_value=None):
            await execute_optimization_task(task_id, ["INVALID_TKR"], request)

    status_resp = await get_optimization_status(task_id)
    assert status_resp["status"] == "failed"
    assert "No data found in Postgres" in status_resp["error"]

    # Verify trace logs
    assert f"execute_optimization_task started for task: {task_id}" in caplog.text
    assert "Fetching OHLCV data from Postgres" in caplog.text
    assert f"Task {task_id} failed: No data found" in caplog.text

@pytest.mark.anyio
async def test_optimization_status_endpoint_not_found():
    """Verify 404 for non-existent task."""
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await get_optimization_status("non-existent-id")
    assert exc.value.status_code == 404
