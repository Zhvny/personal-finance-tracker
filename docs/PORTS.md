# Ports & DB — Alpha

## Dev servers

| Layanan | Port | Perintah |
|---|---|---|
| API legacy monolit | **8444** | `run.bat` — status: legacy, lihat AGENTS.md |
| Gateway microservice | **8444** (docker) | `docker compose up --build` |
| Domain services | **8450–8455** | platform/ledger/portfolio/market/insights/engagement |

## Database

| DB | Pemilik migrasi | Catatan |
|---|---|---|
| `finance_tracker` (Postgres lokal/VPS) | **Alpha** (alembic `migrations/`) | Beta/Delta/Gamma TIDAK boleh DDL ke sini |

## Aturan

- Port 8444 & 8450–8455 terdaftar global di `../PORTS.md`; port baru wajib
  didaftarkan di sana sebelum dipakai.
- Saat migrate ke VPS (HQ247 Fase 5): bind Postgres ke WireGuard IP saja.
