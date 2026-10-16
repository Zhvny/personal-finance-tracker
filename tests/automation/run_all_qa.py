import os
import sys
import unittest

# Add the current directory and MONOREPO ROOT to sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
sys.path.insert(0, _ROOT)

def run_all():
    print("="*60)
    print("FINANCE TRACKER PHASE 2 CORE FINANCIAL FLOWS - QA RUN")
    print("="*60)

    # We only run A, B, C, J as requested
    patterns = ['test_flow_a.py', 'test_flow_b.py', 'test_flow_c.py', 'test_flow_j.py']

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for pattern in patterns:
        path = os.path.join(_HERE, pattern)
        if os.path.exists(path):
            suite.addTests(loader.discover(start_dir=_HERE, pattern=pattern))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n[SUCCESS] All Phase 2 Core Financial Flows passed!")
        sys.exit(0)
    else:
        print("\n[FAILURE] Some flows failed verification.")
        sys.exit(1)

if __name__ == "__main__":
    run_all()
