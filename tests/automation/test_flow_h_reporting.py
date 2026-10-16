import time


def test_flow_h1_behavioral_report(cli_driver, setup_qa_environment, reporter):
    """
    Test Flow H1: Behavioral Finance Report.
    """
    test_name = "Flow H1: Behavioral Report"
    start_time = time.time()

    try:
        # Inputs:
        # 7: Navigate to Behavioral Report (Option 7 in Personal profile)
        # : Press Enter to exit behavioral report pager / continue
        inputs = ["7", ""]
        output = cli_driver.run(inputs)

        # Check output for behavioral keywords
        assert any(k in output.upper() for k in ["BEHAVIORAL", "PSIKOLOGI", "ANALISIS"])

        duration = time.time() - start_time
        reporter.log_result(test_name, "PASSED", "Behavioral report generated successfully.", duration)

    except Exception as e:
        duration = time.time() - start_time
        reporter.log_result(test_name, "FAILED", f"{type(e).__name__}: {str(e)}", duration)
        raise e

def test_flow_h2_business_report(cli_driver, setup_qa_environment, reporter):
    """
    Test Flow H2: Business Quarterly P&L Report.
    """
    test_name = "Flow H2: Business Report"
    start_time = time.time()

    try:
        # Inputs:
        # 8: Open Profile switcher menu
        # 1: Select "Switch Active Profile"
        # 2: Select option 2 (Business profile)
        # : Press Enter to continue after profile switch confirmation
        # 7: Navigate to Quarterly Business Report (Option 7 in Business menu)
        # : Press Enter to exit business report / continue
        inputs = ["8", "1", "2", "", "7", ""]
        output = cli_driver.run(inputs)

        # Verify success message or quarterly keywords in output
        assert any(k in output.upper() for k in ["GENERATING QUARTERLY REPORT", "SUCCESS", "REPORT SAVED", "QUARTERLY"])

        duration = time.time() - start_time
        reporter.log_result(test_name, "PASSED", "Business P&L report generated successfully.", duration)

    except Exception as e:
        duration = time.time() - start_time
        reporter.log_result(test_name, "FAILED", f"{type(e).__name__}: {str(e)}", duration)
        raise e
