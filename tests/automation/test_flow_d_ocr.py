import os
import sqlite3
import time

from test_infrastructure import ensure_profile


def test_flow_d_ocr_integration(cli_driver, setup_qa_environment, reporter):
    """
    Test Flow D: OCR Scanning and Integration into Expense Tracker.
    Uses environment variable OCR_MOCK=true to use the Mock engine.
    """
    test_name = "Flow D: OCR & Integration"
    start_time = time.time()

    data_root = os.path.dirname(os.path.dirname(setup_qa_environment["qa_profile_dir"]))
    # Dummy input lives in the isolated tmp root (never rewrite the tracked fixture).
    dummy_path = os.path.join(data_root, "dummy_receipt.jpg")
    # ExpenseExporter writes under Config.get_cli_data_root(). The repo-wide
    # autouse fixture (tests/conftest.py) pins FINANCE_ROOT_OVERRIDE=<tmp>, which
    # wins over FINANCE_DATA_ROOT, so the child resolves to
    # <tmp>/apps/cli/profiles/<active>/expense_tracker/data/expense.db.
    db_path = os.path.join(
        data_root,
        "apps",
        "cli",
        "profiles",
        "personal",
        "expense_tracker",
        "data",
        "expense.db",
    )

    # Ensure assets directory and dummy file exist
    os.makedirs(os.path.dirname(dummy_path), exist_ok=True)
    with open(dummy_path, "w") as f:
        f.write("mock receipt image content")

    # Pin the active profile so the export path is deterministic
    # regardless of which flow ran before (active profile persists on disk).
    _root = setup_qa_environment["root_dir"]
    assert ensure_profile(
        "personal", _root, os.path.join(_root, "apps", "cli", "main.py")
    ), "could not activate personal profile"

    try:
        # Set OCR_MOCK for the child process via the driver's env snapshot
        # (os.environ set here would NOT propagate: CLIDriver copies env at init).
        cli_driver.env["OCR_MOCK"] = "true"

        # Inputs:
        # 4: Navigate to Scan Menu
        # 1: Select Single Scan
        # dummy_path: Input image path
        # n: Do not edit Starbucks OCR result
        # 3: Export to Expense Tracker (force — deterministic regardless of
        #    auto-classification; option 1 follows the detected type)
        # : Press Enter after success
        # 0: Back from Scan Menu
        inputs = ["4", "1", dummy_path, "n", "3", "", "0"]
        output = cli_driver.run(inputs)

        # Verify output markers
        assert "starbucks" in output.lower()
        assert "Edit data" in output
        assert "EXPORT_DESTINATION" in output
        assert "Exported to expense" in output or "Success" in output

        # Verify Database entry (merchant stored raw; UI uppercases it for display)
        assert os.path.exists(db_path), "Database file not created"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT description, amount FROM expenses WHERE description LIKE '%STARBUCKS%'")
        row = cursor.fetchone()
        conn.close()

        assert row is not None, "Expense record not found in database"
        assert row[1] == 50000, f"Expected amount 50000, got {row[1]}"

        duration = time.time() - start_time
        reporter.log_result(test_name, "PASSED", "OCR scan and export to database successful.", duration)

    except Exception as e:
        duration = time.time() - start_time
        reporter.log_result(test_name, "FAILED", f"{type(e).__name__}: {str(e)}", duration)
        raise e
    finally:
        if "OCR_MOCK" in os.environ:
            del os.environ["OCR_MOCK"]
