# Alpha — Roadmap

> Narasi rencana tingkat atas. Untuk mileston produk lihat `PRD.md §8`; untuk
> inventaris file/status kanonik lihat `docs/PROJECT_MAP.md`/`docs/STATUS.md`;
> untuk utang teknis + trigger lihat `docs/maintenance/HONEY_DEBT.md` (SSOT).

## Status saat ini

Alpha ada di **stage-1 microservice**: entry point resmi `services/*` (gateway `:8444`
+ 6 domain service `:8450`–`:8455`), sementara `apps/api/main.py` masih monolit LEGACY
yang berfungsi. Deployment (compose/k8s) **belum** mengikuti pemecahan layanan — lihat
utang #1/#2/#7 dan blocker di `STATE.md`.

## Fase berjalan

### Fase A — Stabilisasi runtime & integritas data (aktif)

- Isolasi per-profil via Postgres schema-per-profile + `search_path` (2026-09-18)
  sudah berlaku; verifikasi nol kebocoran lintas profil.
- Pindahkan sisa reads dari SQLite legacy ke Postgres profile-scoped.
- Tutup sisa 500/502: `/stocks/*`, `/ml-stocks` (market); `/merchant-map`;
  `/goals/undefined` (lihat `STATE.md` §Known remaining).

### Fase B — Hygiene repo & dokumentasi (aktif)

- Peta + status yang di-generate (anti-basi): `docs/PROJECT_MAP.md`, `docs/STATUS.md`.
- Karantina reversibel duplikat/sampah (tanpa hapus): `docs/_archive/**`, `_quarantine/root/**`.
- 12 root doc + 42 doc per-service (`services/<name>/docs/`).
- Spec: `docs/superpowers/specs/2026-10-12-repo-hygiene-design.md`.

## Utang teknis & trigger

Diambil dari `docs/maintenance/HONEY_DEBT.md` (SSOT). Utang hanya dieksekusi saat
**trigger**-nya tercapai.

| # | Utang | Trigger eksekusi |
|---|---|---|
| 1 | Shared Postgres untuk semua domain | Service butuh scaling/deploy cadence sendiri, ATAU migrasi sering konflik antar domain |
| 2 | Shared image `finance-tracker-api:latest` (7 container) | Trigger sama dengan #1 |
| 3 | Router masih di `packages/api/backend/routers/` (shared lib) | Saat eksekusi #1 |
| 4 | `analytics.py` mencampur segmen behavioral/logs/portfolio | Bareng #3 |
| 5 | `business_analytics` (domain konstruksi) menumpang di ledger | Jika fitur berkembang → service/repo terpisah |
| 6 | Legacy monolith `apps/api/main.py` + `packages/api/api_server.py` | Setelah topology `services/*` stabil 2 minggu di produksi |
| 7 | Compose/k8s tervalidasi struktural saja (Docker tak tersedia di mesin dev) | First `docker compose up` → jalankan smoke test `/health` gateway |

## Battlefront QA (historis)

`docs/planning/MASTER_QA_ROADMAP.md` (v10.0, terakhir diperbarui 2026-05-25) memecah
verifikasi jadi 5 fase. Dokumen itu **era CLI/SQLite** — sebagian item sudah tercakup
oleh isolasi per-profil dan migrasi Postgres, sebagian masih relevan:

1. **Infrastruktur & stabilitas inti** — pathing root, audit `PYTHONPATH`, sinkronisasi dependency.
2. **Integritas finansial & math** — FIFO (partial sell, lot washing, corporate action),
   PPh 21 & FX resolution.
3. **Keamanan data & isolasi multi-profil** — stress test switcher, leak test lintas profil,
   HMAC audit log, disaster recovery.
4. **Validasi layanan AI/analitik** — benchmark OCR ensemble, tuning fuzzy merchant,
   audit weighting Senate/ML.
5. **Orkestrasi API & UI** — latensi middleware, validasi Pydantic, paritas GUI↔CLI.

Karena artefak lama, status item-item di atas **_(belum diverifikasi)_** terhadap kode saat ini.

## Rencana produk

Mileston produk (Q3 2026 – Q2 2027) tetap di **`PRD.md §8`**: stabilisasi core,
primitif platform, ekspansi intelligence, lalu distribusi & sync. `ROADMAP.md` tidak
menduplikasi daftar itu.

## Sumber

- `docs/planning/MASTER_QA_ROADMAP.md` (5 battlefront QA, 2026-05-25).
- `docs/maintenance/HONEY_DEBT.md` (tabel utang + trigger).
- `docs/superpowers/specs/2026-10-12-repo-hygiene-design.md` (fase hygiene & docs).
- `PRD.md §8` (mileston produk), `PRD.md §10.1` (debt register D1–D6).
- `AGENTS.md` (status arsitektur), `STATE.md` (blocker & known remaining).
