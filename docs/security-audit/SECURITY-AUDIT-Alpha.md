# Security Audit — Alpha (FastAPI Microservice)

Tanggal audit: 2026-08-22 · Metode: statis terpandu · Skala: 🟠 TINGGI · 🟡 SEDANG · 🔵 RENDAH

## Postur

**KUAT.** Auth enforcement menyeluruh dan konsisten.

## Temuan baik

- **Scope enforcement menyeluruh**: 39 router, 100+ `Depends(require_scope("read"|"write"))`
  di level router maupun endpoint — tidak ada router telanjang.
- **CORS** dari env `FINANCE_TRACKER_CORS_ORIGINS`, default localhost, tanpa wildcard.
- **Prod compose**: password via `${POSTGRES_PASSWORD}`, bukan hardcoded.
- Internal services tidak publish port di compose — satu pintu = gateway (+ token wajib).

## Temuan & status

| ID | Severity | Isi | Status |
|----|----------|-----|--------|
| S-1 | 🟠 | `docker-compose.yml` dev: postgres `5432:5432` publish semua interface + password `password`. Jangan pernah dipakai apa adanya di VPS publik. | **OPEN** — saat deploy: hapus blok `ports` postgres atau bind `"127.0.0.1:5432:5432"` / WG IP |
| S-2 | 🟡 | Rate limiting belum ada di gateway/Caddy — token tetap bisa brute-force. | OPEN (opsional) — pasang limit di Caddy atau middleware per-IP+token; pola referensi ada di hq-infra relay |
| S-3 | 🟡 | Mode non-docker bind `0.0.0.0` → layanan internal ekspos ke LAN. | **FIXED** — default `HOST=127.0.0.1`; kedua compose setel `HOST=0.0.0.0` eksplisit untuk container |
| S-4 | 🔵 | `apps/web/src/app/layout.tsx:93` `dangerouslySetInnerHTML` untuk JSON-LD. Aman selama `jsonLd` statis. | VIGILANCE — jangan isi dari input user |

## Catatan arsitektur keamanan

Gateway memakai exact-route proxy dari OpenAPI tiap service. Route baru otomatis
ikut ter-proxy — pastikan endpoint internal (mis. `/health*`) tidak sengaja terekspos
publik lewat mekanisme ini.
