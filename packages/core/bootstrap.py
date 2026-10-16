import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

def setup_environment():
    """
    Establish the environment bootstrap for the monorepo.
    1. Resolve project root by searching upwards for a marker.
    2. Inject root, packages/, and apps/ into sys.path and os.environ["PYTHONPATH"].
    """
    # 1. Resolve Root
    # Start search from current file's directory
    current_dir = Path(__file__).resolve().parent
    root = None

    # Primary Search: Look for GEMINI.md (canonical root marker)
    for parent in [current_dir] + list(current_dir.parents):
        if (parent / "GEMINI.md").exists():
            root = parent
            break

    # Secondary Search: Fallback to common markers
    if root is None:
        for parent in [current_dir] + list(current_dir.parents):
            if (parent / "package.json").exists() or (parent / ".git").exists() or (parent / ".setup_done").exists():
                root = parent
                break

    if root is None:
        # Final Fallback: known structure (packages/core/bootstrap.py -> finance-tracker/)
        # We walk up 2 levels from core/
        root = current_dir.parent.parent
        logger.warning(f"BOOTSTRAP WARNING: Root marker not found. Falling back to {root}")

    # Ensure we have absolute path
    root = root.resolve()
    packages_dir = (root / "packages").resolve()
    apps_dir = (root / "apps").resolve()

    # 2. Paths to ensure are present
    target_paths = [
        str(root),
        str(packages_dir),
        str(apps_dir)
    ]

    # 3. Inject into sys.path (Idempotent)
    # We want these at the VERY front to override any shadowed packages
    for p in reversed(target_paths):
        if p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)

    # 4. Export/Update PYTHONPATH for subprocesses
    current_pythonpath = os.environ.get("PYTHONPATH", "")
    existing_paths = [p.strip() for p in current_pythonpath.split(os.pathsep) if p.strip()]

    # Rebuild PYTHONPATH with targets at the front, preserving existing ones
    final_paths = []
    for p in target_paths:
        if p not in final_paths:
            final_paths.append(p)

    for p in existing_paths:
        if p not in final_paths:
            final_paths.append(p)

    os.environ["PYTHONPATH"] = os.pathsep.join(final_paths)

    # 5. Fix for isolated subprocesses on Windows
    # Ensure the directory containing this script is in sys.path if called directly
    if str(current_dir) not in sys.path:
        sys.path.append(str(current_dir))

    return root

# Auto-execute on import
PROJECT_ROOT = setup_environment()

if __name__ == "__main__":
    print(f"Bootstrap complete. Root: {PROJECT_ROOT}")
    print(f"PYTHONPATH: {os.environ.get('PYTHONPATH')}")
    print(f"sys.path[0:3]: {sys.path[0:3]}")
