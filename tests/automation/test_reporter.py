import os
import time
from datetime import datetime


class TestReporter:
    def __init__(self):
        self.results = []
        self.start_time = time.time()

    def log_result(self, test_name, status, message="", duration=0):
        self.results.append({
            "name": test_name,
            "status": status.upper(),
            "message": message,
            "duration": duration,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    def generate_report(self, filepath):
        total_tests = len(self.results)
        passed = len([r for r in self.results if r["status"] == "PASSED"])
        failed = len([r for r in self.results if r["status"] == "FAILED"])
        total_duration = sum([r["duration"] for r in self.results])

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# QA Automation Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Total Duration:** {total_duration:.2f}s\n\n")

            f.write("## Summary\n")
            f.write(f"- **Total Tests:** {total_tests}\n")
            f.write(f"- **Passed:** {passed} ✅\n")
            f.write(f"- **Failed:** {failed} ❌\n\n")

            f.write("## Detailed Results\n")
            f.write("| Test Name | Status | Duration | Message |\n")
            f.write("| --- | --- | --- | --- |\n")
            for r in self.results:
                f.write(f"| {r['name']} | {r['status']} | {r['duration']:.2f}s | {r['message']} |\n")

            if failed > 0:
                f.write("\n## Failure Details\n")
                for r in self.results:
                    if r["status"] == "FAILED":
                        f.write(f"### {r['name']}\n")
                        f.write(f"**Message:**\n```\n{r['message']}\n```\n")

        print(f"Report generated: {filepath}")

if __name__ == "__main__":
    # Smoke test
    reporter = TestReporter()
    reporter.log_result("CLI Start Test", "PASSED", "CLI started successfully", 2.5)
    reporter.log_result("OCR Flow Test", "FAILED", "Timeout waiting for OCR result", 10.2)
    report_path = os.path.join(os.getcwd(), 'docs/maestro/qa_report_smoke.md')
    reporter.generate_report(report_path)
