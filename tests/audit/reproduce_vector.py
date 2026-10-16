import os
import sys
from pathlib import Path

# --- BOOTSTRAP START ---
# Ensure packages/ is in sys.path even if run from outside the root
current_file = Path(__file__).resolve()
root_search = current_file.parent
bootstrap_mod = None

for parent in [root_search] + list(root_search.parents):
    candidate = parent / "packages" / "core" / "bootstrap.py"
    if candidate.exists():
        # Add root to sys.path so we can import packages.*
        root = parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        try:
            import packages.core.bootstrap as bootstrap
            bootstrap.setup_environment()
            bootstrap_mod = bootstrap
        except ImportError:
            # Fallback to direct file execution if package import fails
            import importlib.util
            spec = importlib.util.spec_from_file_location("bootstrap", str(candidate))
            bootstrap_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(bootstrap_mod)
            if hasattr(bootstrap_mod, 'setup_environment'):
                bootstrap_mod.setup_environment()
        break

if not bootstrap_mod:
    print("CRITICAL: Could not locate bootstrap.py. Attempting relative path injection.")
    # Search for GEMINI.md as fallback root detection
    for parent in [root_search] + list(root_search.parents):
        if (parent / "GEMINI.md").exists():
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            break
# --- BOOTSTRAP END ---

import argparse
import importlib.util
from typing import Type

from harness import BaseAuditVector


def load_vector_class(vector_id: str) -> Type[BaseAuditVector]:
    """
    Dynamically load the audit vector class for a given ID.
    Expected file pattern: tests/audit/vectors/vector_{id_safe}.py
    Expected class name: AuditVector_{id_safe}
    """
    id_safe = vector_id.replace('.', '_')
    module_name = f"vector_{id_safe}"
    file_path = os.path.join(os.path.dirname(__file__), "vectors", f"{module_name}.py")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audit vector implementation not found at {file_path}")

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    class_name = f"AuditVector_{id_safe}"
    if not hasattr(module, class_name):
        raise AttributeError(f"Module {module_name} does not contain class {class_name}")

    return getattr(module, class_name)

def run_audit(vector_id: str):
    """Load and execute a specific audit vector."""
    print("\n" + "="*60)
    print(f"ELITE AUDIT: REPRODUCING VECTOR {vector_id}")
    print("="*60 + "\n")

    try:
        vector_class = load_vector_class(vector_id)
        vector_instance = vector_class(vector_id)
        result = vector_instance.run()

        print("\n" + "-"*60)
        print("AUDIT REPORT")
        print("-"*60)
        print(str(result))
        print("-"*60)

        if not result.success:
            sys.exit(1)

    except Exception as e:
        print(f"FATAL: Failed to execute audit vector {vector_id}: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Elite System Audit Reproduction CLI")
    parser.add_argument("vector_id", help="The ID of the failure vector to reproduce (e.g., 1.1)")

    args = parser.parse_args()
    run_audit(args.vector_id)
