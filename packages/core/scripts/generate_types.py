import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from pydantic2ts import generate_typescript_from_pydantic

from packages.core.domain.models import Expense, Income, Investment, SellTransaction


def main():
    models = [Expense, Income, Investment, SellTransaction]
    output_path = Path(__file__).parent.parent.parent / "types" / "index.ts"

    # Ensure directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating types to {output_path}...")

    # generate_typescript_from_pydantic takes a list of models or a module
    # and writes to the specified file
    generate_typescript_from_pydantic(
        "packages.core.domain.models",
        output_path
    )

    print("Done!")

if __name__ == "__main__":
    main()
