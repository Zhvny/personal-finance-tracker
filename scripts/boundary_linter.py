import re
import sys
from pathlib import Path


def lint_boundaries(root_dir: Path) -> int:
    """
    Checks for monorepo boundary violations.
    Forbidden: packages/core -> apps/*
    Forbidden: packages/core -> packages/api
    """
    core_dir = root_dir / "packages" / "core"
    violations = []

    # Patterns for forbidden imports
    forbidden_patterns = [
        re.compile(r"from\s+apps\."),
        re.compile(r"import\s+apps\."),
        re.compile(r"from\s+packages\.api"),
        re.compile(r"import\s+packages\.api"),
    ]

    for py_file in core_dir.rglob("*.py"):
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f, 1):
                    for pattern in forbidden_patterns:
                        if pattern.search(line):
                            violations.append(f"{py_file}:{i}: {line.strip()}")
        except Exception as e:
            print(f"Error reading {py_file}: {e}")

    if violations:
        print("Boundary violations found:")
        for v in violations:
            print(v)
        return 1

    print("No boundary violations found.")
    return 0

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    sys.exit(lint_boundaries(project_root))
