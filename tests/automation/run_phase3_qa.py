import os
import subprocess
import sys

# Set PYTHONPATH to include project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
os.environ["PYTHONPATH"] = project_root + os.pathsep + os.environ.get("PYTHONPATH", "")

scripts = [
    "tests/automation/test_flow_e.py",
    "tests/automation/test_flow_f.py",
    "tests/automation/test_flow_g_i.py"
]

def main():
    print("========================================")
    print("=== STARTING PHASE 3 QA AUTOMATION ===")
    print("========================================")

    results = {}

    for script in scripts:
        print(f"\n[RUNNING] {script}")
        full_path = os.path.normpath(os.path.join(project_root, script))
        cmd = [sys.executable, full_path]
        print(f"Command: {cmd}")
        res = subprocess.run(cmd, capture_output=True, text=True, shell=False)

        if res.returncode == 0:
            print(f"[PASS] {script}")
            results[script] = "PASS"
        else:
            print(f"[FAIL] {script}")
            print("--- STDOUT ---")
            print(res.stdout)
            print("--- STDERR ---")
            print(res.stderr)
            results[script] = "FAIL"

    print("\n" + "="*40)
    print("       PHASE 3 QA SUMMARY")
    print("="*40)
    all_pass = True
    for script, res in results.items():
        print(f"{script:<30}: {res}")
        if res == "FAIL":
            all_pass = False

    if all_pass:
        print("\n[RESULT] ALL PHASE 3 TESTS PASSED")
        sys.exit(0)
    else:
        print("\n[RESULT] SOME TESTS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
