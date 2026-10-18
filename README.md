<div align="center">
  <img src="apps/web/public/og-image.png" alt="Alpha" width="360" />

  **Alpha — Personal Finance Tracker & Wealth Engine**

  ![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688) ![Python 3.12](https://img.shields.io/badge/Python-3.12-3776ab) ![Next.js 15](https://img.shields.io/badge/Next.js-15-000000) ![React 19](https://img.shields.io/badge/React-19-38bdf8) ![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791) ![Docker](https://img.shields.io/badge/Docker-Compose-2496ed)

  Bahasa: **Indonesia** · [English](README.en.md)
</div>

Platform pelacak keuangan pribadi, portofolio investasi, dan analitik AI cerdas berbasis arsitektur microservices. Menggabungkan manajemen kas multi-profil, pelacakan FIFO multi-aset (saham, kripto, emas), pemindaian struk OCR ensemble, optimasi portofolio genetik, model prediksi ML, serta gamifikasi reward mingguan dan analisis perilaku finansial.

## Fitur Utama

- **Ledger & Anggaran** - pencatatan multi-rekening, kategori kustom, pelacakan pengeluaran & pemasukan, transaksi berulang, estimasi *safe-to-spend*, dan peramalan saldo masa depan.
- **Portofolio & Investasi** - pelacakan aset komprehensif (saham IDX, kripto, emas) dengan kalkulasi FIFO P/L otomatis, riwayat transaksi dividen, dan perbandingan performa.
- **Market Analytics & ML** - analisis teknikal real-time, model klasifikasi XGBoost Sniper, optimasi bobot portofolio berbasis algoritma genetik, dan sistem konsensus *Agent Senate*.
- **Insights & Receipt OCR** - pemindaian struk belanja ensemble 3-engine (Tesseract + EasyOCR + PaddleOCR) dengan *majority voting*, deteksi anomali otomatis, dan *AI financial health score*.
- **Reward & Gamifikasi** - rotasi self-reward mingguan (12 item dari pool 300+ item bilingual, 5 kategori, 25 tingkat harga), carry-over klaim 14 hari, pelacak streak menabung, dan peringkat disiplin.
- **Platform & Keamanan** - isolasi multi-profil (Pribadi & Bisnis), autentikasi CIA Triad + tanda tangan HMAC, pembatasan laju (*rate limiting*), audit log SQLite, dan integrasi bot notifikasi Telegram.

## Arsitektur Sistem

Topologi microservices terdistribusi dengan API Gateway terpusat yang merutekan request ke enam domain service independen:

```text
                       ┌──────────────┐
   Browser / Web ─────►│   Gateway    │ :8444  Reverse proxy otomatis
   CLI / Mobile ──────►│  (FastAPI)   │        berbasis OpenAPI spec
                       └──────┬───────┘
      ┌──────────┬───────────┬┴─────────┬────────────┬────────────┐
      ▼          ▼           ▼          ▼            ▼            ▼
   platform    ledger    portfolio    market     insights    engagement
    :8450      :8451       :8452       :8453       :8454       :8455
   Autentikasi Transaksi   Investasi   Saham IDX   OCR Struk   Perilaku
   Multi-Profil Anggaran   FIFO P/L    Model ML    AI Advisor  Reward Pool
   Notifikasi  Peramalan   Laporan     Optimizer   Anomali     Rotasi Mingguan
      └──────────┴───────────┴──────────┬─┴────────────┴────────────┘
                                        ▼
                                 PostgreSQL 16
```

| Service | Port | Domain & Tanggung Jawab |
|---|---|---|
| `gateway` | 8444 | Entry point publik, reverse proxy HTTP otomatis, WebSocket proxy (`/ws/*`) |
| `platform` | 8450 | Autentikasi, manajemen profil, audit log, notifikasi WebSocket, bot Telegram |
| `ledger` | 8451 | Pengeluaran, pemasukan, kategori, anggaran, safe-to-spend, peramalan saldo |
| `portfolio` | 8452 | Investasi multi-aset, kalkulasi FIFO P/L, rekapitulasi dividen, ringkasan dasbor |
| `market` | 8453 | Analisis saham, model XGBoost ML, algoritma genetik, Agent Senate, scheduler |
| `insights` | 8454 | OCR struk belanja ensemble, pemetaan merchant, deteksi anomali pengeluaran |
| `engagement` | 8455 | Indeks keuangan perilaku (FBS), rotasi reward mingguan, carry-over klaim |

## Stack Teknologi

| Layer | Teknologi |
|---|---|
| Frontend | [Next.js](https://nextjs.org) 15 (Kanonik) + [Vite](https://vite.dev) 5 / [React](https://react.dev) 19, Tailwind CSS, Recharts, Context i18n ID/EN |
| Backend | Python 3.12, [FastAPI](https://fastapi.tiangolo.com), Uvicorn, Pydantic v2, HTTPX, Prisma Client Python |
| Analitik & ML | pandas, NumPy, yfinance, XGBoost, Algoritma Genetik, Ollama (opsional) |
| OCR Struk | Ensemble [Tesseract](https://github.com/tesseract-ocr/tesseract) + [EasyOCR](https://github.com/JaidedAI/EasyOCR) + [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) |
| Database | [PostgreSQL](https://www.postgresql.org) 16 (skema multi-profil terisolasi) + SQLite lokal |
| Orkestrasi | [Turborepo](https://turbo.build), pnpm 11, Docker Compose, Kubernetes (`k8s/`) |

## Struktur Direktori

```text
personal-finance-tracker/
├── apps/
│   ├── web/                 # Dashboard kanonik Next.js 15 (App Router, Tailwind, TypeScript)
│   ├── cli/                 # TUI terminal Textual (Rich) interaktif
│   └── api/                 # Wrapper legacy monolith (backward-compatible)
├── packages/
│   ├── api/                 # Library backend bersama: router, autentikasi CIA, otomatisasi
│   ├── core/                # Clean Architecture: domain, layanan aplikasi, infrastruktur
│   │   ├── domain/          # Entitas bisnis, engine reward, model matematis
│   │   ├── application/     # Kasus penggunaan: ledger, portofolio, insight, OCR
│   │   └── infrastructure/  # Repositori PostgreSQL, seeder reward pool 300 item
│   ├── database/            # Skema Prisma & jembatan migrasi
│   ├── types/               # Definisi tipe TypeScript bersama
│   └── web/                 # Aplikasi web legacy Vite (React 19, i18n ID/EN)
├── services/                # Runtime Microservices (Kanonik)
│   ├── gateway/             # Gateway reverse proxy (:8444)
│   ├── platform/            # Service platform & user (:8450)
│   ├── ledger/              # Service transaksi & anggaran (:8451)
│   ├── portfolio/           # Service investasi & laporan (:8452)
│   ├── market/              # Service pasar modal & ML (:8453)
│   ├── insights/            # Service OCR & analitik struk (:8454)
│   ├── engagement/          # Service reward & scheduler rotasi (:8455)
│   └── runtime/             # Bootstrap bersama, logging, circuit breaker, rate limiter
├── migrations/              # Migrasi skema SQL bernomor (001–021)
├── k8s/                     # Manifes Kubernetes: gateway, domain-services, ingress
├── scripts/                 # Utilitas administrasi & simulasi 26 minggu
├── docker-compose.yml       # Topologi Docker development
├── docker-compose.prod.yml  # Topologi Docker production
└── README.md
```

Jelajahi kode: [services](services/) · [packages](packages/) · [apps](apps/) · [migrations](migrations/) · [k8s](k8s/)

## Cara Run (Development)

Prasyarat: Python 3.12+, Node.js 20+ (22 disarankan), pnpm 11, PostgreSQL 16 (atau Docker).

### Opsi A — Docker Compose (Topologi Lengkap)

```bash
# Salin konfigurasi environment
cp .env.example .env

# Jalankan seluruh service, gateway, database, dan web
docker compose up --build

# Akses aplikasi:
# Web Dashboard  → http://localhost:3000
# API Gateway    → http://localhost:8444  (Health check: http://localhost:8444/health)
```

### Opsi B — Lokal tanpa Docker

```bash
# 1. Pasang dependensi workspace (frontend & tooling)
pnpm install

# 2. Pasang dependensi Python
pip install -r requirements.prod.txt

# 3. Jalankan seluruh microservices + gateway
# Windows:
./run-services.bat
# Linux/macOS: jalankan python -m services.<nama_service>.main di masing-masing terminal

# 4. Jalankan frontend (terminal terpisah)
pnpm --filter @finance-tracker/web dev    # Dashboard Next.js (:3000)
# atau
pnpm --filter finance-tracker-gui dev    # Dashboard Vite legacy (:5173)
```

## Verifikasi & Pengujian

```bash
# Jalankan seluruh unit test suite Python
pytest tests/unit/

# Jalankan simulasi rotasi reward 26 minggu
python scripts/simulate_rotation.py

# Verifikasi kompilasi TypeScript frontend
pnpm --filter @finance-tracker/web exec tsc --noEmit

# Verifikasi build frontend legacy
pnpm --filter finance-tracker-gui build
```

## License

`MIT LICENSE` (Copyright © 2026 Zhvny).
