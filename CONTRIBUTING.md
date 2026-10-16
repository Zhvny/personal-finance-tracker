# Kontribusi ke Alpha

Alpha adalah personal finance platform lokal-pertama (Python FastAPI + Next.js).
Kontrak kerja agen **wajib** ada di `AGENTS.md` — baca dulu sebelum mengerjakan apa pun.
Dokumen ini merangkum alur kerja, gate kualitas, dan larangan yang berlaku saat ini.

## Ringkas arsitektur

- **Entry point resmi:** `services/*` (gateway `:8444` + 6 domain service `:8450`–`:8455`).
- **`apps/api/main.py` = LEGACY monolit** — jangan tambah fitur baru di sana.
- Port kanonik: `docs/PORTS.md` dan `.env.example`.
- Narasi sistem: `ARCHITECTURE.md`; daftar area/status: `docs/PROJECT_MAP.md`.

## Prasyarat

- Python 3.12 (`requires-python = ">=3.12,<3.13"`, lihat `pyproject.toml`)
- Node.js 20+ (22 direkomendasikan), pnpm
- PostgreSQL 16 (atau `docker compose up postgres`)
- Tesseract OCR (opsional), Ollama (opsional)
- `git`

## Setup

```bash
# Dependency Python (pinned production set)
pip install -r requirements.prod.txt

# Dependency workspace JS
pnpm install

# Pre-commit hooks (lihat .pre-commit-config.yaml)
pip install pre-commit
pre-commit install
```

`setup.bat` juga tersedia untuk bootstrap di Windows.

## Alur kerja wajib (plan → approve → eksekusi)

Untuk tugas non-trivial (lebih dari 1 file), ikuti pagar `AGENTS.md §Aturan operasional`:

1. **Plan** — sajikan scope, file yang disentuh, output yang diharapkan.
2. **Approve** — berhenti; tunggu jawaban manusia.
3. **Eksekusi** — kerjakan hanya langkah yang disetujui.
4. **Verify** — jalankan gate yang relevan, tunjukkan bukti.
5. **Commit** — commit kecil per unit kerja, setelah approval eksplisit.

## Gate kualitas

```bash
pytest                    # suite Python (testpaths = tests/); coverage fail_under = 40
ruff check .              # lint (line-length 120, target py312)
ruff format .             # formatter (quote-style double)
pre-commit run --all-files
pnpm lint                 # eslint + ruff
pnpm test                 # turbo test (vitest)
```

- **Ruff**: `ruff.toml` menyeleksi `E,F,W,I`. Sebagian aturan legacy di-`ignore`
  (mis. `E402`, `F841`) sebagai utang yang didokumentasikan; lihat komentar di `ruff.toml`.
- **Coverage**: `[tool.coverage.report].fail_under = 40` di `pyproject.toml`.
- **Pre-commit** (`.pre-commit-config.yaml`) menjalankan `detect-secrets`, `gitleaks`,
  `ruff --fix`, dan `ruff-format`.

### Catatan `detect-secrets`

Baseline `.secrets.baseline` saat ini dibaca sebagai UTF-16LE oleh hook dan memicu
`Unable to read baseline`. Sampai baseline diperbaiki (atau hook dipatch), lewati
hook itu untuk commit doc, mis.:

```bash
SKIP=detect-secrets pre-commit run --all-files
```

Ini bukan izin menambah secret: `gitleaks` tetap jalan dan `.env*`, sertifikat, serta
state runtime tetap wajib di luar history.

## Konvensi commit

- Stage **file spesifik**, jangan pernah `git add .`.
- Commit kecil, pesan jelas, satu unit kerja per commit.
- Jangan commit tanpa approval eksplisit manusia (`AGENTS.md §1`).
- `.md` di root ter-`ignore` oleh `.gitignore` (`*.md`) — tambahkan doc baru
  secara eksplisit dengan `git add -f <file.md>`.

## Larangan keras

- **Jangan sentuh `migrations/`** untuk skema milik domain lain — satu database = satu pemilik migrasi.
- **Jangan sentuh `apps/api/main.py`** untuk fitur baru (LEGACY).
- **Jangan tambah dependency** (`pyproject.toml`, `requirements*.txt`, `package.json`)
  tanpa approval eksplisit; jangan jalankan `pip install`/`pnpm add`/`uv add` tanpa izin.
- **Jangan hapus file** tanpa approval (termasuk yang tampak dead code).
- **Jangan commit** `.env*`, `packages/api/certs/*`, cache/state runtime
  (`*.db`, `market_sync_backoff.json`, `active_profile.txt`) — semuanya sudah ter-ignore.
- **Isolasi per-profil (2026-09-18)** tidak boleh dilanggar: `schema.prisma` **tanpa**
  `multiSchema`/`@@schema`; jangan menambahkan `@@schema("alpha_*")` kembali. Field Prisma
  baru wajib mirror ke `per_profile_ddl.py` **dan** ALTER schema profil existing.
  Lihat `docs/SCHEMA_AUTHORITY.md`.
- Semua route `/api/*` wajib `require_scope(...)` (termasuk `/api/config`); hanya
  `/health*` publik. Jangan pernah log nilai API key / bearer token.
- Jangan jadikan `docs/planning/**`, `.ai/**` sebagai acuan arsitektur (artefak sesi lama).

## Windows gotchas

1. Jangan menulis `.env`/JSON via PowerShell (`Set-Content` menambah BOM).
2. Kirim body JSON via node/file tanpa BOM, bukan quoting curl PowerShell.
3. Encoding semua doc: UTF-8 **tanpa BOM** (pakai editor/tool, bukan `Set-Content`).

## Sumber

- `AGENTS.md` (status arsitektur, aturan operasional, larangan keras, isolasi per-profil).
- `.pre-commit-config.yaml` (hook `detect-secrets`, `gitleaks`, `ruff`, `ruff-format`).
- `ruff.toml` (select/ignore, per-file-ignores, `[format]`).
- `pyproject.toml` (`requires-python`, dependency, `[tool.pytest.ini_options]`, `[tool.coverage.*]`).
- `README.md` (Prasyarat, Quick Start, Development), `setup.bat`.
- `STATE.md` (catatan `detect-secrets` 2026-09-05, session isolasi per-profil 2026-09-18).
- `docs/PORTS.md`, `docs/SCHEMA_AUTHORITY.md`.
