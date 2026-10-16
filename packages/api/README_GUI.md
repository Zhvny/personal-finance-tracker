# Finance Tracker GUI — By Zhvny

React + FastAPI frontend yang terhubung ke semua CLI module via API bridge (`api_server.py`).

---

## Cara Menjalankan

### Cara cepat — `setup.bat` (Windows)

Dari root monorepo (`finance-tracker/`), double-click atau jalankan:

```
setup.bat
```

Script otomatis:
1. Install Python dependencies (`pip install -r requirements.txt`)
2. Install Node dependencies (`npm install`)
3. Generate `.env` + API key baru (jika belum ada)
4. Generate TLS cert self-signed (jika belum ada)
5. Tampilkan menu launcher

```
  1. Command Line Interface
  2. Graphical User Interface
  3. Exit
```

Pilih **2** — script membuka API server dan React dev server di window terpisah, lalu otomatis membuka browser ke `http://localhost:5173`.

> Setup hanya berjalan sekali (ditandai file `.setup_done` di root). Run berikutnya langsung ke menu.

### Manual

Butuh **3 terminal** yang berjalan bersamaan:

```bash
# Terminal 1 — API bridge (wajib)
cd finance-tracker-gui

# Generate API key (pertama kali)
python generate_key.py
# Salin output ke .env:
# FINANCE_TRACKER_API_KEY=<hasil>

# Generate TLS cert (pertama kali, untuk HTTPS/LAN)
python generate_cert.py

# Jalankan server
python api_server.py
# → https://0.0.0.0:8443

# Terminal 2 — React dev server (wajib)
npm install
npm run dev
# → http://localhost:5173

# Terminal 3 — Scheduler otomatis (opsional)
python backend/automation/scheduler.py
```

> **Ollama (AI lokal):** Jalankan `ollama serve` di terminal tersendiri sebelum membuka GUI.
> Model yang direkomendasikan: `llama3.1:8b`

```bash
ollama pull llama3.1:8b
ollama serve
```

---

## Setup & Konfigurasi

Salin `.env.example` ke `.env` dan isi variabelnya:

```bash
cp .env.example .env
```

| Variable | Default | Keterangan |
|---|---|---|
| `FINANCE_TRACKER_API_KEY` | (wajib) | Master Bearer token — generate dengan `python generate_key.py` |
| `FINANCE_TRACKER_DEV_MODE` | `0` | Set `1` untuk skip auth saat dev lokal |
| `FINANCE_TRACKER_RATE_LIMIT` | `60` | Request/menit/IP |
| `FINANCE_TRACKER_CORS_ORIGINS` | `http://localhost:5173,https://localhost:8443` | Origin yang diizinkan (pisah koma) |
| `FINANCE_TRACKER_HOST` | `0.0.0.0` | Bind address |
| `FINANCE_TRACKER_PORT` | `8443` | HTTPS port |
| `FINANCE_TRACKER_CERT` | `certs/server.crt` | Path TLS cert |
| `FINANCE_TRACKER_KEY` | `certs/server.key` | Path TLS key |

### LAN Access (HP/tablet)

1. Generate cert: `python generate_cert.py` — otomatis include semua IP LAN sebagai SAN
2. Install `certs/server.crt` di perangkat (lihat `HTTPS_SETUP.md`)
3. Tambah IP LAN ke `.env`:
   ```
   FINANCE_TRACKER_CORS_ORIGINS=http://localhost:5173,https://localhost:8443,https://192.168.1.100:8443
   ```
4. Akses dari perangkat: `https://<IP-PC>:8443`

---

## Security

Semua endpoint (kecuali `/health`) dilindungi Bearer token. Frontend wajib login sebelum bisa akses halaman manapun.

| Layer | Implementasi |
|---|---|
| Auth | Bearer token via `Authorization` header — otomatis di-inject `apiFetch()` |
| Token storage | `sessionStorage` — terhapus saat browser ditutup, tidak pernah di URL/DOM |
| HTTPS | Semua traffic TLS — `API_BASE` hardcoded ke `https://` |
| Rate limit | 60 req/menit/IP (configurable) |
| Audit log | Setiap request dicatat ke `data/audit_log.db` |
| Scope | Router `read` / `write` / `admin` |

---

## Struktur Direktori

```
finance-tracker-gui/
├── api_server.py        ← App factory FastAPI (~586 baris)
├── generate_cert.py     ← Generator TLS cert self-signed (LAN IPs sebagai SAN)
├── generate_key.py      ← Generator API key (secrets.token_hex(32))
├── .env.example         ← Dokumentasi semua env variable
├── .gitignore           ← certs/, .env, *.key di-exclude
├── HTTPS_SETUP.md       ← Panduan trust cert: Android / iOS / Windows / macOS
│
├── backend/
│   ├── security/
│   │   └── core.py          ← CIA Triad + AAA (auth, rate limit, audit)
│   ├── routers/
│   │   ├── deps.py          ← Shared state + DB helpers (leaf node)
│   │   ├── __init__.py      ← Passive manifest
│   │   ├── expenses.py      ← scope=write
│   │   ├── income.py        ← scope=write
│   │   ├── investments.py   ← scope=write
│   │   ├── receipts.py      ← scope=write
│   │   ├── advanced.py      ← scope=write
│   │   ├── behavioral.py    ← scope=read
│   │   ├── balances.py      ← scope=write
│   │   ├── rewards.py       ← scope=write
│   │   ├── merchant.py      ← scope=write
│   │   ├── scheduler.py     ← scope=write
│   │   ├── analytics.py     ← scope=read
│   │   └── ai.py            ← scope=read
│   ├── ai/
│   │   ├── provider_strategy.py   ← _detect_provider(), _ai_chat(), _ai_chat_vision()
│   │   └── ai_rule_engine.py      ← Rule-based fallback (zero-dependency)
│   ├── behavioral/
│   │   └── data_aggregator.py     ← _gather_financial_data(), _build_financial_context()
│   ├── automation/
│   │   └── scheduler.py           ← APScheduler daemon
│   ├── expenses/
│   │   └── recurrence_detector.py
│   ├── finance/
│   │   ├── allocation_engine.py
│   │   └── saving_rules.json
│   ├── receipt/
│   │   └── merchant_memory.py
│   └── rewards/
│       └── reward_unlock.py
│
├── certs/               ← gitignored
│   ├── server.crt       ← Bagikan ke perangkat yang perlu trust server ini
│   └── server.key       ← Jangan pernah dibagikan; chmod 600
│
├── data/
│   ├── goals.db         ← cash_split, manual_balances, transfer_log, reward_state
│   ├── budget.db        ← Budget limits per kategori per bulan
│   ├── merchant_map.db  ← Learned merchant → category mapping
│   ├── networth_history.db ← Net worth snapshots harian
│   └── audit_log.db     ← Log semua request (dibuat otomatis)
│
└── src/
    ├── main.jsx                 ← AuthProvider > BrowserRouter > App
    ├── App.jsx                  ← Root layout: sidebar + routing + lazy loading
    ├── AuthContext.jsx          ← Login screen + sessionStorage token lifecycle
    ├── icons.jsx                ← Central icon registry
    ├── components.jsx           ← UI atoms: Tabs, Modal, Toast, PLBadge, dll
    ├── animations.jsx           ← Page transition + sidebar animation
    ├── styles/
    │   ├── dark-style.css
    │   └── light-style.css
    ├── finance/
    │   ├── useApi.js            ← SEMUA API calls — auto-inject Bearer token
    │   ├── constants.js         ← API_BASE, CATEGORIES, fmt, CAT_COLOR
    │   ├── dashboard.jsx
    │   ├── advanced.jsx
    │   ├── AnalyticsPanel.jsx
    │   ├── TrendChart.jsx
    │   └── NetWorthHistoryChart.jsx
    ├── module/                  ← Lazy-loaded CRUD modules
    │   ├── expense_tracker.jsx
    │   ├── income_tracker.jsx
    │   ├── investment_tracker.jsx
    │   └── receipt_reader.jsx
    ├── behavioral/
    │   ├── BehavioralDashboard.jsx
    │   ├── ImpulsiveSpending.jsx
    │   ├── RiskExposure.jsx
    │   ├── NetWorthHeatmap.jsx
    │   ├── AIInsightPanel.jsx   ← SSE streaming
    │   ├── AIStatusBadge.jsx    ← Provider selector
    │   ├── behavioralEngine.js
    │   └── useBehavioralData.js
    └── rewards/
        ├── LustDashboard.jsx
        ├── LustShop.jsx
        ├── lustEngine.js
        ├── lustStore.js
        └── rewardCatalogue.js
```

---

## Database

### CLI databases (shared dengan GUI — jangan hapus)

| File | Path dari root monorepo | Tabel |
|---|---|---|
| `expense.db` | `apps/cli/expense_tracker/data/` | `expenses` |
| `income.db` | `apps/cli/income_tracker/data/` | `incomes` |
| `portfolio.db` | `apps/cli/investment_tracker/data/` | `investments`, `sell_transactions`, `historical_prices` |
| `goals.db` | `apps/cli/advanced_features/data/` | `goals` — shared CLI + GUI |

### GUI-only databases (`data/`)

| File | Tabel | Keterangan |
|---|---|---|
| `goals.db` | `cash_split`, `manual_balances`, `transfer_log`, `reward_state` | Balance system + reward state |
| `budget.db` | `budgets` | Limit per kategori per bulan |
| `merchant_map.db` | `merchant_map` | Learned merchant mappings |
| `networth_history.db` | `networth_snapshots` | Snapshot harian dari scheduler |
| `audit_log.db` | `audit_log` | Security audit (auto-dibuat) |

> **JANGAN hapus file `.db` apapun — semua data finansial tersimpan di sana.**

---

## AI Insight Engine

Provider dipilih otomatis saat startup, urutan prioritas:

| Prioritas | Provider | Syarat |
|---|---|---|
| 1 | **Claude API** | `ANTHROPIC_API_KEY` di-set dan reachable |
| 2 | **Ollama** | `ollama serve` berjalan di `localhost:11434` |
| 3 | **Rule-based** | Fallback zero-dependency — selalu tersedia |

### Ganti model Ollama

Dari GUI: klik badge provider (pojok kanan atas halaman Behavioral) → pilih **Ollama** → sub-panel model muncul.

Dari API:
```bash
curl -X POST https://localhost:8443/api/ai/provider \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"provider": "ollama", "model": "llama3.1:8b"}'
```

Model yang didukung:

| Model | Ukuran | Catatan |
|---|---|---|
| `llama3.1:8b` | ~5GB | **Direkomendasikan** — prioritas pertama |
| `llama3.2` | ~2GB | Lebih ringan |
| `mistral` | ~4GB | Alternatif |
| `gemma2` | ~5GB | Google |
| `phi3` | ~2GB | Ringan, Microsoft |

Token cap: 768 untuk semua model (OOM prevention pada 6GB RAM).

---

## Receipt Reader

Di mobile, drop zone menampilkan dua tombol terpisah:

- **Pilih dari Galeri** — membuka file picker galeri foto
- **Buka Kamera** — langsung membuka kamera belakang

Di desktop: klik area drop zone atau seret file PNG/JPG/WebP.

**Claude Vision AI** digunakan jika `ANTHROPIC_API_KEY` tersedia. Fallback: OCR ensemble (Tesseract + EasyOCR + PaddleOCR majority voting).

---

## Balance System

```
bank_savings   = max(0, SUM(incomes.amount) − SUM(expenses.amount))  ← auto-hitung tiap GET /api/balances
physical_cash  = split informational, diatur via Transfer UI
emergency_fund = satu-satunya field yang bisa diedit manual
cash_on_hand   = (physical_cash + bank_savings) − emergency_fund
crypto         = READ-ONLY dari portfolio.db
```

- `bank_savings` tidak perlu di-set manual — otomatis mencerminkan kondisi all-time
- `emergency_fund` tidak boleh melebihi `bank_savings`
- Transfer antara `physical_cash` ↔ `bank_savings` tidak mengubah Total Credit

---

## Saving Allocation

Konfigurasi di `backend/finance/saving_rules.json`. Default bucket:

| Bucket | % | Label |
|---|---|---|
| expenses | 50 | Biaya Hidup |
| savings | 20 | Tabungan |
| investment | 20 | Investasi |
| emergency | 10 | Dana Darurat |

Edit langsung via file JSON, lalu restart `api_server.py`.

---

## Reward System

```
public/rewards/
├── rewards-index.json          ← ["reward-1", "reward-2", ...]
└── reward-N/
    ├── manifest.json
    ├── photo_1.jpg
    └── video_1.mp4
```

**Format `manifest.json`:**
```json
{
  "id": "reward-1",
  "title": "Judul Reward",
  "cost": 500,
  "season": 0,
  "tier": "basic",
  "type": "photo",
  "contents": [
    { "file": "photo_1.jpg", "type": "photo", "caption": "" }
  ]
}
```

Tier: `basic | mid | premium | ultra`. Season: 0-indexed (Season 1 = `"season": 0`).

Untuk menambah reward baru:
```bash
python backend/rewards/cli.py
```

---

## Mobile

Dioptimalkan untuk:
- **OPPO A9 2020** — 720×1600px fisik → 360px CSS (2× DPR)
- **iPhone XR** — 828×1792px fisik → 414px CSS (2× DPR)

Fitur:
- Sidebar off-canvas via hamburger, backdrop tap untuk tutup
- Semua modul berat di-lazy load (`React.lazy` + `Suspense`)
- Receipt Reader: tombol Galeri + Kamera terpisah
- TrendChart tooltip: overlay centered + backdrop + tombol tutup di mobile
- Behavioral tabs: icon-only pada ≤380px
- Modal: bottom sheet pada ≤380px
- Touch target minimal 44×44px
- `font-size: 16px` pada semua input (cegah iOS auto-zoom)

---

## Prinsip Arsitektur

| Prinsip | Implementasi |
|---|---|
| High Cohesion | Setiap file punya satu tanggung jawab |
| Low Coupling | Komponen hanya terima data via props |
| DRY | API calls → `useApi.js` · icons → `icons.jsx` · format → `constants.js` |
| Clean Architecture | Interface (JSX) → Application (hooks) → Data (routers) → SQLite |
| Security by Default | Semua endpoint require Bearer token; HTTPS enforced |
| Zero Emoji | Semua icon dari react-icons via `icons.jsx` |

---

## Troubleshooting

| Gejala | Solusi |
|---|---|
| `401 Unauthorized` di semua endpoint | Pastikan `FINANCE_TRACKER_API_KEY` di `.env` dan sudah login di GUI |
| Browser warning "Not Secure" | Install `certs/server.crt` di perangkat — lihat `HTTPS_SETUP.md` |
| `bank_savings` selalu 0 | Pastikan `api_server.py` jalan dan ada data di `income.db` |
| AI Insights error 503 | Set `ANTHROPIC_API_KEY` atau jalankan `ollama serve` |
| Model Ollama tidak berubah | Pastikan `ollama pull <model>` sudah selesai, pilih ulang dari badge |
| HP tidak bisa akses dari LAN | Tambah IP LAN ke `FINANCE_TRACKER_CORS_ORIGINS` di `.env` |
| Investment sold masih muncul | Klik **Clean DB** — filter `status != 'sold'` aktif |
| Saving rules tidak berubah | Edit `backend/finance/saving_rules.json`, restart `api_server.py` |
