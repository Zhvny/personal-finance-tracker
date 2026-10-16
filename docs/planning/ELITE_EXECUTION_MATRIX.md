# ⚡ ELITE EXECUTION MATRIX: INFRASTRUCTURE & STABILITY (PART 1)

This matrix converts the 10 failure vectors of Part 1 into actionable tasks, explicit audit procedures, and binary DoD criteria.

---

## 🏗️ PART 1: Infrastructure & Structural Integrity

| ID | Task (The Work) | Audit/Red-Team Procedure (The Test) | Definition of Done (DoD) |
| :--- | :--- | :--- | :--- |
| **1.1** | **Marker-Chain Root Detection**<br>Implement `find_root()` in `packages/core/infra/root.py` using `pathlib`. Must find root by locating `GEMINI.md` + `.git` + `package.json`. | **Procedur:** Create a symlinked folder 5 levels deep inside `node_modules`. Run `python -c "from packages.core.infra.root import find_root; print(find_root())"`. | **Criteria:** Returns the absolute canonical root path regardless of current working directory or symlink depth. |
| **1.2** | **Thread-Safe Config Singleton**<br>Wrap `Config` initialization in a thread-safe singleton (using `threading.Lock`) to prevent race conditions during root discovery. | **Procedure:** Use a Python script to spawn 100 concurrent threads, each attempting to access `Config.BASE_DIR` simultaneously. | **Criteria:** Zero `FileExistsError` or `OSError`; `find_root()` is called exactly ONCE across all threads. |
| **1.3** | **Monorepo Dependency Linter**<br>Create `scripts/lint_imports.py` to parse AST and enforce boundary rules (No imports from `apps/` into `packages/`). | **Procedure:** Manually inject an import `from apps.cli.main import X` into a core utility. Run `python scripts/lint_imports.py`. | **Criteria:** Script exits with Code 1 and identifies the exact line and file of the boundary violation. |
| **1.4** | **Idempotent sys.path Injection**<br>Implement logic to append project root to `sys.path` ONLY if it's not already present or represented by a different absolute path. | **Procedure:** Call the injection logic 10x in a loop. Inspect `sys.path` for duplicate or redundant entries. | **Criteria:** `sys.path` contains exactly one entry for the canonical project root. |
| **1.5** | **Path Truncation Guard**<br>Implement `path_verifier.py` to check for paths exceeding 240 chars. Use UNC paths (`\\?\`) where supported on Windows. | **Procedure:** Create a dummy directory structure with a path length of 255 characters. Attempt to write a file using the core repository. | **Criteria:** Application detects the risk and either handles it via UNC or raises a clear `PathTooLongError` before failing. |
| **1.6** | **Atomic PID Management**<br>Rewrite `scheduler.py` to use `portalocker` or similar for file locking on `.pid` files. Ensure lock is released on `SIGKILL/SIGTERM`. | **Procedure:** Start the scheduler, then `taskkill /F` the process. Attempt to restart the scheduler immediately. | **Criteria:** Scheduler restarts successfully by detecting the stale/unlocked PID file and overwriting it safely. |
| **1.7** | **Circular Import Break**<br>Refactor `Config` and `Logger` to use dependency injection or move shared constants to a primitive `constants.py` file. | **Procedure:** Run `python -c "from packages.core.infrastructure.config import Config"`. | **Criteria:** No `ImportError: cannot import name X from Y` occurs during any core module initialization. |
| **1.8** | **BOM-Aware .env Parser**<br>Replace `python-dotenv` with a custom parser or pre-processor that strips BOM (Byte Order Mark) and handles UTF-16 encoding. | **Procedure:** Save a `.env` file in UTF-16 with BOM via Notepad. Attempt to read a key-value pair via the application. | **Criteria:** Key-value pairs are parsed correctly without junk characters in the variable names. |
| **1.9** | **Permission Integrity Check**<br>Add `check_perms.py` to `setup.bat`. Verify write access to `C:\ProgramData` and current workspace. | **Procedure:** Run `setup.bat` as a Standard User (non-admin). | **Criteria:** Setup aborts early with a "High-Signal" error message: "Admin privileges required for [Specific Folder] access." |
| **1.10** | **Orphan Process Reaper**<br>Implement a "Heartbeat" mechanism where child fetchers kill themselves if the parent PID (CLI) is no longer active. | **Procedure:** Start the CLI and a background price fetcher. Force-kill the CLI process. Wait 10 seconds. Check Task Manager. | **Criteria:** Background process `price_fetcher.exe/py` is no longer in the process list. |

---
**Status:** ELITE EXECUTION MATRIX (PART 1)
**Verification Level:** MANDATORY RED-TEAMING
**Last Updated:** 25-05-2026 (22:30)
