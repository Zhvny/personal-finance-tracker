# Design Document: Orchestral Merge Cleanup 2026-05-27

## Problem Statement
The repository contains local branches that have been partially or fully merged, but the process has left behind conflict markers in several files (including `.ai/TASKS.md`, `README.md`, and some source files like `genetic.py`). Additionally, stale local branches need to be removed to maintain repository health.

## Objectives
1. Identify all files with git conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).
2. Resolve conflict markers by choosing the appropriate version (preferring `HEAD` for metadata and current project state).
3. Verify the integrity of the application after cleanup.
4. Delete merged local branches: `qa-testing-cli`, `seo-gui`, `testing`.

## Strategy
1. **Discovery**: Use `grep_search` to find all files with conflict markers.
2. **Resolution**:
    - For `.ai/TASKS.md` and `README.md` files, merge the content or prefer `HEAD`.
    - For source code (`genetic.py`), carefully resolve the conflict to ensure functionality.
3. **Verification**:
    - Run `python apps/cli/main.py maintain -a` to check system health.
    - Run existing tests in `tests/`.
4. **Cleanup**: Use `git branch -d` to delete merged branches.

## Risk Assessment
- **Low**: Most conflicts are in documentation/metadata.
- **Medium**: `genetic.py` requires careful manual resolution to avoid breaking the genetic optimizer.

## Proposed Changes
- Modify files identified in Discovery to remove markers.
- Delete branches `qa-testing-cli`, `seo-gui`, `testing`.
