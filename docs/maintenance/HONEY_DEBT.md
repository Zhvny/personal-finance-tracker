# Alpha — Tech Debt Ledger (stage-1 microservice)

Setiap item wajib punya **trigger**: kondisi konkret kapan debt ini dieksekusi.
Tanpa trigger = "later" = never. Review ledger ini tiap akhir fase besar.

| # | Debt | Dampak sekarang | Trigger eksekusi |
|---|---|---|---|
| 1 | Shared Postgres untuk semua domain service | Satu DB down = semua down; tidak bisa scale per-domain; migration lintas domain saling sentuh | Service tertentu butuh scaling/deploy cadence sendiri, ATAU migration sering konflik antar domain |
| 2 | Shared image `finance-tracker-api:latest` untuk 7 container | Build/redeploy all-or-nothing; ukuran image membawa dep semua service | Trigger sama dengan #1 — pecah per-service Dockerfile saat split DB |
| 3 | Router tetap di `packages/api/backend/routers/` (shared lib), service cuma subset-import | Import graph masih bisa menyilang antar domain diam-diam | Saat eksekusi #1: pindahkan kode router ke `services/<name>/api/` |
| 4 | `analytics.py` mencampur segmen behavioral/logs/portfolio dalam satu router (parkir di insights) | Route /api/logs/recent & /api/behavioral/* dilayani service "salah" secara domain | Eksekusi bareng #3 |
| 5 | `business_analytics` (domain proyek konstruksi) parkir di ledger | Domain asing menumpang service keuangan | Kalau fiturnya berkembang → extract jadi service sendiri atau pindah repo Beta |
| 6 | Legacy monolith `apps/api/main.py` + `packages/api/api_server.py` masih hidup | Dua entry point; risiko fix hanya diterapkan di satu sisi | Setelah 2 minggu topology services stabil di produksi → hapus legacy + `run.bat` mode GUI migrasi ke gateway |
| 7 | Compose/k8s tervalidasi struktural saja (docker tidak tersedia di mesin dev) | Runtime behavior (healthcheck timing, depends_on) belum terbukti | First `docker compose up` di mesin/host yang punya Docker → jalankan smoke test `/health` gateway |
