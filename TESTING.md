# Alpha — Testing

> Cara menjalankan dan menggerbangi test suite. Untuk test **per-service**, lihat
> `services/<name>/docs/TESTING.md` (generated). Untuk test tooling docs, lihat
> `tests/tools/`.

## 1. Perintah gate

```bash
python -m pytest            # test suite (testpaths = ["tests"])
ruff check .                # lint
```

Gate CI yang sebenarnya (`.github/workflows/ci.yml`, job `api`):

```bash
poetry run ruff check .
poetry run pytest --ignore=tests/automation
poetry run pip-audit
```

Catatan: CI meng-`--ignore=tests/automation` (butuh sandbox Postgres/CLI), dan
menambah `pip-audit` yang tidak ada di gate lokal.

## 2. Konfigurasi (terverifikasi dari `pyproject.toml`)

| Setting | Nilai |
|---|---|
| `testpaths` | `["tests"]` |
| `python_files` | `["test_*.py"]` |
| `python_classes` | `["Test*"]` |
| `python_functions` | `["test_*"]` |
| `addopts` | `-p no:warnings` |
| `asyncio_mode` | `auto` (pytest-asyncio) |
| coverage `source` | `["apps", "packages"]` |
| coverage `fail_under` | **40** |

`tests/conftest.py` memasang fixture `autouse` yang men-set `USE_SQLITE_ONLY=true`
sehingga unit test berjalan tanpa Postgres.

Lint (`ruff.toml`): `line-length = 120`, `target-version = "py312"`,
`select = ["E","F","W","I"]`. Banyak kode mekanis di-ignore (mis. `E501 E701 E402
E722 F841`) dan sebagian debt sisa didokumentasikan sebagai komentar di `ruff.toml`.

## 3. Status saat ini (terukur 2026-10-12)

| Perintah | Hasil |
|---|---|
| `python -m pytest --collect-only -q` | **842 tests collected** (18.12s) |
| `ruff check . --statistics` | exit **0** — tidak ada temuan (bersih) |

Angka di atas dari run nyata di working tree ini. Bila suite berubah, perbarui angka
di sini atau tandai `_(belum diverifikasi)_`.

## 4. Struktur suite (`tests/`)

| Direktori | File `test_*.py` | Fokus |
|---|---|---|
| `tests/unit/` | 60 | unit domain + engine |
| `tests/integration/` | 16 | integrasi API/DB/eksternal |
| `tests/automation/` | 18 | flow CLI/GUI driver (di-skip CI) |
| `tests/audit/` | 8 | invariant audit/security |
| `tests/regression/` | 4 | regresi (mis. atomicity sale) |
| `tests/stability/` | 3 | reliability/stability |
| `tests/reconciliation/` | 1 | rekonsiliasi |
| `tests/tools/` | 2 | test tooling docs (`gen_service_docs`, `alpha_hygiene`) |

Di root `tests/` ada runner QA one-off (`qa_bug_hunt.py`, `run_exhaustive_qa.py`,
`exhaustive_qa_*.py`) dan test standalone (`test_circuit_breaker.py`,
`test_schema_isolation.py`, dll).

## 5. Strategi & riwayat

- **Target pipeline 3-layer** (unit → integration → E2E, Docker-native) dirancang di
  `docs/superpowers/specs/2025-09-16-automated-testing-design.md`. Saat ini
  `docker-compose.test.yml` **belum ada** — desain itu belum terealisasi penuh.
- **Ruff sweep 2026-08-24** (`docs/maintenance/2026-08-24-ruff-sweep-and-test-triage.md`):
  7.352 → 0 error (5.252 auto-fixed, commit `6eb5956`). Triage suite saat itu:
  **745 passed, 7 failed, 1 error, 1 skipped** (~6m20s); sweep terbukti tidak
  menambah regresi. Failure persisten saat itu didaftar di dokumen tersebut.

## 6. Menambah test

Ikuti konvensi: file `tests/<layer>/test_*.py`, fungsi `test_*`, class `Test*`.
Gunakan fixture `tests/conftest.py` (SQLite-only). Jalankan `ruff check .` dan
`python -m pytest -q` sebelum menyatakan selesai.

## Sumber

- `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`).
- `ruff.toml`.
- `tests/**`, `tests/conftest.py`, `tests/tools/**`.
- `.github/workflows/ci.yml`, `.github/workflows/e2e.yml`.
- `docs/maintenance/2026-08-24-ruff-sweep-and-test-triage.md`.
- `docs/superpowers/specs/2025-09-16-automated-testing-design.md`.
- Output nyata: `python -m pytest --collect-only -q`; `ruff check . --statistics`.
- Inventaris generated: `services/*/docs/TESTING.md`, `docs/PROJECT_MAP.md`.

## 7. Gate split: fast vs slow

### Fast gate (per push / PR)

Runs in `ci.yml` job `api`:

```bash
pytest tests/unit tests/tools -m "not live_pg" -q
```

No Postgres CLI subprocess, no live services. Completes in < 2 min.

### Slow gate (nightly + `workflow_dispatch` + PR label `run-slow`)

Runs in `.github/workflows/slow.yml`, two jobs:

| Job | What it runs |
|---|---|
| `live-pg` | `pytest tests/automation -m live_pg -q` (live Postgres CLI flows) |
| `e2e-compose` | `docker compose up` + `pnpm test:e2e:ci` (full stack E2E) |

Trigger manually via **Actions → Slow → Run workflow**, or label a PR `run-slow`.

### `live_pg` marker

Tests that require a live Postgres connection must be decorated:

```python
import pytest
pytestmark = pytest.mark.live_pg  # module-level
# — or per-function —
@pytest.mark.live_pg
def test_something(): ...
```

Include a skip guard so the test degrades gracefully in environments without Postgres:

```python
pytest.importorskip("psycopg2")  # skip if driver absent

def test_example():
    if not _pg_reachable():
        pytest.skip("postgres not reachable")
    ...
```

**Note:** markers must be registered in `pyproject.toml` under `[tool.pytest.ini_options] markers`
to suppress `PytestUnknownMarkWarning`. Registration is owned by the `pyproject.toml` workstream
and tracked separately from this file.
