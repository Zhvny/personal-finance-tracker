# Quarantine manifest

Reversible moves only — nothing is ever deleted. To revert, move each `dest` back to
`src` (`git mv` when mode=tracked, a plain rename when untracked).

## 2026-10-12T11:40:42Z

| mode | src | dest |
|---|---|---|
| tracked | `docs/planning/superpowers` | `docs/_archive/superpowers` |
| tracked | `docs/AUDIT-quality-perf-2026-08-23.md` | `docs/_archive/AUDIT-quality-perf-2026-08-23.md` |
| tracked | `docs/AUDIT-security-full-2026-08-23.md` | `docs/_archive/AUDIT-security-full-2026-08-23.md` |
| tracked | `docs/perlu di perbaiki` | `docs/_archive/perlu-di-perbaiki` |
| untracked | `wallet_search.txt` | `_quarantine/root/wallet_search.txt` |
| untracked | `scratch_commit_msg.txt` | `_quarantine/root/scratch_commit_msg.txt` |
| untracked | `database.db` | `_quarantine/root/database.db` |
| untracked | `.coverage` | `_quarantine/root/.coverage` |
| untracked | `check_passwords.py` | `_quarantine/root/check_passwords.py` |
| untracked | `fix-dev-mode.py` | `_quarantine/root/fix-dev-mode.py` |
| untracked | `update_model.py` | `_quarantine/root/update_model.py` |
