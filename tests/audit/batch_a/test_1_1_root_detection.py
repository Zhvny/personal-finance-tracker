import shutil
import tempfile
from pathlib import Path

import pytest

from packages.core.infrastructure.config import Config


@pytest.fixture
def temp_project_structure():
    temp_dir = Path(tempfile.mkdtemp())
    try:
        root = temp_dir / "project"
        root.mkdir()
        (root / ".setup_done").touch()

        packages = root / "packages" / "core" / "infrastructure"
        packages.mkdir(parents=True)

        yield root
    finally:
        shutil.rmtree(temp_dir)

def test_root_detection_logic(temp_project_structure):
    root = temp_project_structure
    infra_file = root / "packages" / "core" / "infrastructure" / "config.py"

    # Use the staticmethod get_root if it accepts start_path
    detected = Config.get_root(infra_file)
    assert detected == root
