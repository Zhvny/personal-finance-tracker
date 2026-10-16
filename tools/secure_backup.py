import shutil
from datetime import datetime
from pathlib import Path


def backup_databases():
    # Use dynamic path resolution for independence
    root_dir = Path(__file__).resolve().parent.parent
    backup_base = root_dir / "data" / "backups" / "sqlite_structured"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = backup_base / timestamp

    print(f"Starting structured backup to: {backup_dir}")

    db_files = list(root_dir.rglob("*.db"))

    for db_file in db_files:
        # Create relative path to preserve structure
        rel_path = db_file.relative_to(root_dir)
        target_path = backup_dir / rel_path

        # Ensure target directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file
        shutil.copy2(db_file, target_path)
        print(f"Backed up: {rel_path}")

    print(f"\nBackup complete. Total files: {len(db_files)}")
    print(f"Location: {backup_dir}")

if __name__ == "__main__":
    backup_databases()
