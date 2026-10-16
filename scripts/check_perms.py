import os
import sys


def check_write_access(path):
    try:
        test_file = os.path.join(path, '.perm_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except Exception:
        return False

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    critical_paths = [
        root,
        os.path.join(root, 'data'),
        os.path.join(root, 'apps'),
        os.path.join(root, 'logs'),
    ]

    for path in critical_paths:
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except Exception:
                print(f"FAILED: Cannot create {path}")
                sys.exit(1)

        if not check_write_access(path):
            print(f"FAILED: No write access to {path}")
            sys.exit(1)

    print("SUCCESS: Permission integrity verified")
    sys.exit(0)

if __name__ == "__main__":
    main()
