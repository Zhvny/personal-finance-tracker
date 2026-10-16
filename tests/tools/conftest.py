"""Make ``scripts/alpha_hygiene.py`` importable as a top-level module.

Kept local to ``tests/tools`` on purpose: the root ``tests/conftest.py`` is not ours to edit.
"""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
