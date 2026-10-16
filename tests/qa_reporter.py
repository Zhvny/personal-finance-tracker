import json
import time
from pathlib import Path
from typing import Any, Dict, List


class QAReporter:
    """Aggregates results from test flows and generates summaries."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.log_dir = project_root / "tests" / "logs"
        self.results: List[Dict[str, Any]] = []
        self.start_time = time.time()
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def add_result(self, flow_id: str, name: str, success: bool, duration: float, error: str = None):
        """Adds a single flow result."""
        self.results.append({
            "flow_id": flow_id,
            "name": name,
            "status": "PASS" if success else "FAIL",
            "duration_sec": round(duration, 2),
            "error": error
        })

    def generate_summary(self):
        """Generates JSON and Markdown summaries."""
        total_duration = time.time() - self.start_time
        summary = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_flows": len(self.results),
            "passed": len([r for r in self.results if r["status"] == "PASS"]),
            "failed": len([r for r in self.results if r["status"] == "FAIL"]),
            "total_duration_sec": round(total_duration, 2),
            "results": self.results
        }

        # JSON Report
        json_path = self.log_dir / "exhaustive_qa_summary.json"
        with open(json_path, "w") as f:
            json.dump(summary, f, indent=4)

        # Markdown Report
        md_path = self.log_dir / "exhaustive_qa_summary.md"
        with open(md_path, "w") as f:
            f.write("# Exhaustive QA Results Summary\n\n")
            f.write(f"- **Timestamp**: {summary['timestamp']}\n")
            f.write(f"- **Total Flows**: {summary['total_flows']}\n")
            f.write(f"- **Passed**: {summary['passed']}\n")
            f.write(f"- **Failed**: {summary['failed']}\n")
            f.write(f"- **Total Duration**: {summary['total_duration_sec']}s\n\n")

            f.write("## Detailed Results\n\n")
            f.write("| Flow | Name | Status | Duration | Error |\n")
            f.write("|------|------|--------|----------|-------|\n")
            for r in self.results:
                f.write(f"| {r['flow_id']} | {r['name']} | {r['status']} | {r['duration_sec']}s | {r['error'] or '-'} |\n")

        print(f"\n[REPORTER] Summary generated: {json_path}")
        print(f"[REPORTER] Summary generated: {md_path}")
        return summary
