# Alpha — Installation

> Cara menyiapkan lingkungan dev lokal. Untuk port & pemilik DB lihat `docs/PORTS.md`;
> untuk inventaris area repo lihat `docs/PROJECT_MAP.md`.

## 1. Prasyarat

- Python 3.12+
- Node.js 20+ (22 direkomendasikan), pnpm 11
- PostgreSQL 16 (atau `docker compose up postgres`)
- Opsional: Tesseract OCR (scan struk), Ollama (AI advisor lokal)

## 2. Quick Start — Docker (direkomendasikan)

```bash
cp .env.example .env          # isi SECRET_KEY dll.
docker compose up --build     # gateway + 6 service + postgres + web
# web → http://localhost:3000
# API → http://localhost:8444  (gateway health: /health)
```

`docker compose up` otomatis memuat `docker-compose.override.yml` (mount hot-reload,
Postgres ter-expose di `127.0.0.1:15432`).

## 3. Quick Start — proses lokal (tanpa Docker)

```bash
pnpm install                          # deps workspace (web/packages)
pip install -r requirements.prod.txt  # deps Python backend
python -m services.<name>.main        # jalankan satu service, mis. services.ledger.main
```

> README menyebut `run-services.bat` untuk boot semua service sekaligus, tetapi file
> itu **tidak ada** di repo saat ini — jalankan tiap service manual via
> `python -m services.<name>.main`. _(belum diverifikasi)_

Monolit legacy (deprecated tapi masih fungsional): mount **semua** router di satu port;
pekerjaan baru harus lewat `services/`. _(perintah runner legacy belum diverifikasi)_

## 4. Setup Windows (`setup.bat`)

`setup.bat` = wizard first-time setup Windows (butuh hak Administrator). Yang dilakukan:

1. Cek Python & Node.js.
2. Install deps Python (`apps/cli`, `packages/api`, `apps/api`, `stock_analyzer`) +
   paket tambahan (yfinance, apscheduler, xgboost, pytesseract, scikit-learn, pandas-ta).
3. Install deps Node (`packages/web`).
4. Buat `packages/web/.env` bila belum ada.
5. Menu: CLI atau GUI.

> `setup.bat` berorientasi pada stack **legacy** (`packages/api`, `packages/web`, `apps/cli`)
> dan fallback Python 3.10 — bukan alur service `services/*`. Untuk runtime microservice,
> pakai §2/§3.

## 5. Environment Variables

Semua nilai ada di `.env.example` (port registry otoritatif: gateway 8444, domain 8450–8455).

| Variable | Default | Catatan |
|---|---|---|
| `ALPHA_GATEWAY_PORT` | `8444` | Port publik gateway |
| `ALPHA_GATEWAY_TARGETS` | peer localhost | Override URL downstream (compose/k8s mengisi ini) |
| `ALPHA_SERVICE_PORT` | per-service | Override port di dalam container |
| `DATABASE_URL` | — | Postgres DSN bersama (stage-1) |
| `SECRET_KEY` | — | **Wajib**; config gagal boot tanpa ini |
| `FINANCE_TRACKER_CORS_ORIGINS` | localhost | Origin browser yang diizinkan |
| `ENABLE_TELEGRAM_POLL` | `0` | Opt-in Telegram bot long-polling (service platform) |

Jangan commit `.env`. `*.env` sudah ter-ignore.

## 6. Jalankan & verifikasi

```bash
python -m services.<name>.main   # jalankan satu service
pnpm dev                         # turbo dev (web + packages)
pnpm lint                        # eslint + ruff
pnpm test                        # turbo test (vitest)
python -m pytest tests/          # suite Python
ruff check .                     # lint Python (line-length 120, py312)
```

Health per service: `/health` (live), `/health/ready` (kesiapan DB), `/info`
(metadata terautentikasi). Agregat gateway: `GET :8444/health`.
Log berotasi ke `logs/<service-name>.log`.

## Sumber

- `README.md` §Prerequisites, §Quick Start, §Environment Variables, §Development.
- `.env.example`.
- `setup.bat`.
- `docs/PORTS.md`.
- `AGENTS.md` (Windows gotchas, perintah gate test/lint).
- `services/runtime/bootstrap.py` (health endpoint, port resolution).
