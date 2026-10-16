import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
OUT = ROOT / "requirements.prod.txt"
HEADER = "# GENERATED from pyproject.toml \u2014 do not edit\n"


def desired() -> str:
    deps = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["dependencies"]
    return HEADER + "".join(f"{d}\n" for d in deps)


def main() -> None:
    want = desired()
    if "--check" in sys.argv:
        if OUT.read_text(encoding="utf-8") != want:
            print("drift: requirements.prod.txt stale, run python scripts/sync_requirements.py")
            sys.exit(1)
        return
    OUT.write_text(want, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
