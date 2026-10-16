# Tech Debt & Migration Ledger — Alpha

Satu-satunya daftar utang keputusan migrasi monolit → microservice.
Aturan: setiap entri punya **pemicu** (kapan wajib dieksekusi) — utang tanpa
pemicu berarti permanen. Tanggal masuk: 2026-08-22.

| ID | Area | Utang | Pemicu eksekusi | Status |
|----|------|-------|-----------------|--------|
| TD-1 | Scheduler | Dua pemilik potensial: `apps/api/main.py` (MarketScheduler legacy) vs `services/runtime/bootstrap.py` (`scheduler_enabled`). Kontrak: **hanya satu boleh jalan**. Belum ada penegakan. | Saat services ambil alih scheduling produksi: matikan permanen jalur monolit + tambah `pg_advisory_lock("alpha-market-scheduler")` di startup kedua jalur | MITIGATED 2026-08-22 — lease `system.scheduler_lease` (acquire/renew/release) dipasang di `MarketScheduler.start()`; fail-closed, dual-run mustahak terlepas entry point. Retire jalur monolit tetap menunggu momen take-over. Lapis kedua: gerbang awal `packages/api/backend/automation/scheduler_lock.py` (`pg_try_advisory_lock`, fail-closed) di kedua entry point sebelum MarketScheduler dibangun |
| TD-2 | Observability | Gateway belum generate/forward `X-Request-ID`; hanya bootstrap yang setup logging. Satu request gagal = N log terpisah tanpa kunci penyambung. CORS sudah allow header-nya. | PR pertama yang menyentuh gateway middleware: bikin UUID, forward downstream, echo di response error, log tiap baris | DONE 2026-08-22 — gateway: warisi/generate + forward + echo (termasuk 404/502) + log error ber-ID; service: `audit_middleware` set contextvar + echo header; `_setup_logging` mencetak `[%(request_id)s]` |
| TD-3 | Config | Drift monolit ↔ services (`ALLOWED_ORIGINS`, dll terdefinisi dua dunia selama transisi). | Saat ada config baru kedua kalinya: pindahkan ke satu modul settings bersama, atau tambah langkah doctor pembanding nilai efektif | DONE 2026-08-22 — ternyata `bootstrap.py` sudah import `apps.api.config.settings` (sumber tunggal, drift struktural tak mungkin); ditambah `scripts/config_doctor.py` (5/5 lolos) untuk validasi env/secret/CORS/cert/port registry |
| TD-4 | Market data | OHLCV tersimpan sebagai blob JSON per `(ticker, period)` — tak bisa diagregasi via SQL; tiap pembaca menanggung biaya parse penuh di Python. | ≥2 layanan membaca OHLCV **atau** latensi query universe audit > X detik → migrasi baris-per-bar | OPEN |
| TD-5 | Smoke test | Tidak ada uji paritas rute: total rute gateway vs router legacy tidak diverifikasi otomatis; satu router gagal daftar = fitur lenyap senyap. | Sebelum deklarasi "monolit mati": skrip bandingkan jumlah/daftar rute legacy vs via-gateway, masuk CI | OPEN |
| TD-6 | Gateway | WebSocket `/ws/*` (platform) tidak diproxy gateway — klien lama yang hardcode `:8444` akan putus diam-diam saat migrasi penuh. | Inventaris klien WS; jika >0 klien langsung-ke-platform tak bisa diubah → dukung proxy WS di gateway | OPEN |
| TD-7 | Database | Shared Postgres + shared image (stage-1) — disengaja, tercatat juga di AGENTS.md & compose. | Service pertama yang butuh scale/deploy cadence sendiri → split DB/image | ACCEPTED |
| TD-8 | Migrasi DB | Selama fase shared-DB: kepemilikan migrasi skema harus tunggal (alembic `migrations/`); layanan lain read-only terhadap schema; DDL ad-hoc dilarang lewat file migrasi. | Berlaku sekarang; langgar = review blocker | ENFORCED-NOW |
| TD-9 | Deployment | docker-compose dev sudah topologi penuh (7 container); verifikasi manifest `k8s/` + `docker-compose.prod.yml` mengikuti, termasuk healthcheck/readinessProbe memakai `/health/live`. | Sebelum deploy non-dev pertama | OPEN |
| TD-10 | Ports | Registry port: 8444 gateway, 8450–8455 domain services (tercatat di AGENTS.md + compose). Jangan alokasikan manual di luar tabel ini. | Bentrok port pertama dengan dev server lain → pindahkan ke satu file config | MITIGATED |

## Keputusan lintas-project (bukan utang, tapi kontrak)

- **Delta frozen**: scaffold Delta menunggu gerbang Alpha mantap — membuat
  scaffold dari template monolit = melahirkan legacy baru. Kloning layout
  `services/*` saat unfreeze.
- **Beta ↔ Gamma**: audit tumpang-tindih komponen/auth 30 menit; overlap >30%
  → ekstrak package workspace bersama; tidak → dokumentasikan alasan dua app.
  **Hasil audit (2026-08-22)**: dependensi produksi sama hanya 4/26 gabungan
  (~15%, murni next/react/lucide); 11 file ts/tsx path-identik — semuanya
  boilerplate UI-kit & layout (`components/ui/*`, `theme-provider`, login,
  health route). **Keputusan: TIDAK diekstrak** — overlap di bawah ambang,
  duplikasi yang ada adalah pola UI-kit standar. Dua app tetap hidup karena
  membeda audiens/fitur (Beta = app utama + Prisma, Gamma = PWA offline).
