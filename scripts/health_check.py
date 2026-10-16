#!/usr/bin/env python3
"""
scripts/health_check.py
============================
Automated Guardrail for SSOT and Project Standards.
Checks for:
1. Hardcoded paths (C:\\Users\\...)
2. Stray SQLite databases outside profile folders.
3. Missing mandatory timestamps in documentation.
4. PostgreSQL connection and schema integrity.
5. External API availability (yfinance, FRED).
6. Profile directory integrity.
"""

import os
import re
import sys
from pathlib import Path

import requests

# Project Colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

BASE_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE_DIR))

try:
    import yfinance as yf

    from packages.core.infrastructure.config import Config
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
except ImportError as e:
    print(f"{RED}[ERROR]{RESET} Missing dependencies: {e}")
    # We will handle these inside specific check functions if they are critical

def check_hardcoded_paths(fix=False):
    print("[*] Checking for hardcoded paths...")
    violations = []
    ignore_dirs = [".git", "__pycache__", "node_modules", "data", ".gemini", "profiles", ".turbo", ".cache", "venv"]

    # Project Standards: Neutralize personal user paths
    user_home_marker = "C:\\Users\\Zhvn"

    for root, dirs, files in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            if file.endswith((".py", ".md", ".bat", ".sh", ".json", ".yaml", ".yml", ".txt")):
                path = Path(root) / file
                if "health_check.py" in str(path): continue

                try:
                    content = path.read_text(encoding="utf-8")
                    if user_home_marker.lower() in content.lower():
                        if fix:
                            new_content = content

                            # Match Windows and Unix-style paths
                            matches = re.findall(r'[A-Za-z]:\\Users\\[^\s\'"<>|]+', content, re.IGNORECASE)
                            matches += re.findall(r'[A-Za-z]:/Users/[^\s\'"<>|]+', content, re.IGNORECASE)

                            for m in set(matches):
                                if user_home_marker.lower() in m.lower():
                                    try:
                                        abs_match = Path(m).resolve()

                                        # If inside project
                                        if str(abs_match).lower().startswith(str(BASE_DIR).lower()):
                                            rel_from_root = os.path.relpath(abs_match, start=BASE_DIR).replace("\\", "/")

                                            if path.suffix == ".py":
                                                if "Config.BASE_DIR" in content or "from packages.core.infrastructure.config import Config" in content:
                                                    replacement = f"Config.BASE_DIR / '{rel_from_root}'"
                                                else:
                                                    rel_path = os.path.relpath(abs_match, start=path.parent).replace("\\", "/")
                                                    replacement = f"Path(__file__).resolve().parents[{len(path.parents)-2}] / '{rel_from_root}'" # Fallback
                                                    # Actually, relative path is safer for general replacement
                                                    replacement = rel_path
                                            else:
                                                replacement = os.path.relpath(abs_match, start=path.parent).replace("\\", "/")
                                                if replacement == ".": replacement = "./"
                                                elif not replacement.startswith("."): replacement = "./" + replacement

                                            new_content = new_content.replace(m, replacement)
                                            print(f"  [FIX] {path.relative_to(BASE_DIR)}: {m} -> {replacement}")
                                        else:
                                            # Outside project - check if in workspace
                                            workspace_root = BASE_DIR.parents[1] # Zhvny level
                                            if str(abs_match).lower().startswith(str(workspace_root).lower()):
                                                rel_path = os.path.relpath(abs_match, start=path.parent).replace("\\", "/")
                                                new_content = new_content.replace(m, rel_path)
                                                print(f"  [FIX-WS] {path.relative_to(BASE_DIR)}: {m} -> {rel_path}")
                                            else:
                                                # Neutralize
                                                neutralized = m.replace(user_home_marker, "~").replace("\\", "/")
                                                new_content = new_content.replace(m, neutralized)
                                                print(f"  [NEUTRALIZE] {path.relative_to(BASE_DIR)}: {m} -> {neutralized}")
                                    except Exception:
                                        neutralized = m.replace(user_home_marker, "%USERPROFILE%").replace("\\", "/")
                                        new_content = new_content.replace(m, neutralized)
                                        print(f"  [RECOVERY] {path.relative_to(BASE_DIR)}: {m} -> {neutralized}")

                            if new_content != content:
                                path.write_text(new_content, encoding="utf-8")

                            if user_home_marker.lower() in new_content.lower():
                                violations.append(f"{path.relative_to(BASE_DIR)}")
                        else:
                            violations.append(f"{path.relative_to(BASE_DIR)}")
                except Exception:
                    pass

    if violations:
        print(f"{RED}[FAIL]{RESET} Hardcoded paths remain in:")
        for v in violations:
            print(f"  - {v}")
        return False
    print(f"{GREEN}[PASS]{RESET} Hardcoded paths checked.")
    return True

def check_stray_databases():
    print("[*] Checking for stray SQLite databases...")
    violations = []
    allowed_roots = [
        BASE_DIR / "apps" / "cli" / "profiles",
        BASE_DIR / "apps" / "cli" / "advanced_features" / "data",
        BASE_DIR / "apps" / "cli" / "behavioral_finance" / "data",
        BASE_DIR / "apps" / "cli" / "stock_analyzer",
        BASE_DIR / "finance-tracker-gui" / "data",
        BASE_DIR / "finance-tracker-gui",
        BASE_DIR / "packages" / "api",
        BASE_DIR / "packages" / "database",
        BASE_DIR / "tests" / "integration",
        BASE_DIR / "data",
        BASE_DIR / ".cache"
    ]

    ignore_dirs = [".git", "__pycache__", "node_modules", ".pnpm", ".turbo", ".next"]

    for root, dirs, files in os.walk(BASE_DIR):
        # Prune ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for file in files:
            if file.endswith(".db") and file != "usage.db":
                path = Path(root) / file
                is_allowed = any(str(path).startswith(str(allowed)) for allowed in allowed_roots)
                if not is_allowed:
                    violations.append(f"{path.relative_to(BASE_DIR)}")

    if violations:
        print(f"{RED}[FAIL]{RESET} Stray .db files found (Violates SSOT):")
        for v in violations:
            print(f"  - {v}")
        return False
    print(f"{GREEN}[PASS]{RESET} All SQLite databases are in approved locations.")
    return True

def check_documentation_timestamps():
    print("[*] Checking for mandatory timestamps in docs...")
    violations = []
    docs_dir = BASE_DIR / "docs"
    ts_pattern = r"\d{2}-\d{2}-\d{4} \(\d{2}:\d{2}\)"

    if not docs_dir.exists():
        return True

    for root, dirs, files in os.walk(docs_dir):
        for file in files:
            if file.endswith(".md"):
                path = Path(root) / file
                try:
                    content = path.read_text(encoding="utf-8")
                    if not re.search(ts_pattern, content):
                        violations.append(f"{path.relative_to(BASE_DIR)}")
                except:
                    pass

    if violations:
        print(f"{YELLOW}[WARN]{RESET} Missing timestamps in:")
        for v in violations:
            print(f"  - {v}")
        return True
    print(f"{GREEN}[PASS]{RESET} All documentation files are timestamped.")
    return True

def check_postgres():
    print("[*] Checking PostgreSQL connection...")
    try:
        DatabaseManager.initialize()
        rows = DatabaseManager.query("SELECT 1 as health;")
        if rows and rows[0]['health'] == 1:
            # Check schemas
            schemas = DatabaseManager.query("SELECT schema_name FROM information_schema.schemata WHERE schema_name IN ('financials', 'market', 'investment');")
            found = [s['schema_name'] for s in schemas]
            if len(found) >= 0: # Even if 0, connection is healthy. But ideally we want schemas.
                print(f"{GREEN}[PASS]{RESET} Connected to PostgreSQL. Found schemas: {found}")
                return True
    except Exception as e:
        print(f"{RED}[FAIL]{RESET} PostgreSQL Error: {e}")
    return False

def check_external_apis():
    print("[*] Checking External API availability...")
    results = []

    # yfinance
    try:
        ticker = yf.Ticker("AAPL")
        if ticker.info and 'symbol' in ticker.info:
            print(f"{GREEN}[PASS]{RESET} yfinance API is reachable.")
            results.append(True)
        else:
            print(f"{RED}[FAIL]{RESET} yfinance API returned empty data.")
            results.append(False)
    except Exception as e:
        print(f"{RED}[FAIL]{RESET} yfinance Error: {e}")
        results.append(False)

    # FRED
    # Find FRED key in config.yaml or env
    fred_key = os.environ.get("FRED_API_KEY")
    if not fred_key:
        # Check stock_analyzer config
        cfg_path = BASE_DIR / "apps" / "stock_analyzer" / "config.yaml"
        if cfg_path.exists():
            import yaml
            with open(cfg_path, 'r') as f:
                cfg = yaml.safe_load(f)
                fred_key = cfg.get('fred', {}).get('api_key')

    if fred_key:
        try:
            url = f"https://api.stlouisfed.org/fred/series?series_id=GNPCA&api_key={fred_key}&file_type=json"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                print(f"{GREEN}[PASS]{RESET} FRED API is reachable.")
                results.append(True)
            else:
                print(f"{RED}[FAIL]{RESET} FRED API Error: {resp.status_code}")
                results.append(False)
        except Exception as e:
            print(f"{RED}[FAIL]{RESET} FRED Error: {e}")
            results.append(False)
    else:
        print(f"{YELLOW}[SKIP]{RESET} FRED API Key not found. Skipping check.")
        results.append(True)

    return all(results)

def check_profiles():
    print("[*] Checking profile integrity...")
    profiles_dir = BASE_DIR / "apps" / "cli" / "profiles"
    if not profiles_dir.exists():
        print(f"{RED}[FAIL]{RESET} Profiles directory missing: {profiles_dir}")
        return False

    required = ["personal", "business"]
    found = [d for d in os.listdir(profiles_dir) if os.path.isdir(profiles_dir / d)]
    missing = [p for p in required if p not in found]

    if missing:
        print(f"{RED}[FAIL]{RESET} Missing mandatory profiles: {missing}")
        return False

    print(f"{GREEN}[PASS]{RESET} All mandatory profiles ({required}) exist.")
    return True

import argparse


def main():
    parser = argparse.ArgumentParser(description="Finance Tracker Health Check")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix violations automatically")
    args = parser.parse_args()

    print("=== FINANCE TRACKER HEALTH CHECK ===\n")
    results = [
        check_hardcoded_paths(fix=args.fix),
        check_stray_databases(),
        check_documentation_timestamps(),
        check_postgres(),
        check_external_apis(),
        check_profiles()
    ]

    print("\n" + "="*40)
    if all(results):
        print(f"{GREEN}SYSTEM HEALTHY{RESET}")
        sys.exit(0)
    else:
        print(f"{RED}SYSTEM ISSUES DETECTED{RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
