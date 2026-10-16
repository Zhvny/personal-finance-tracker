# Alpha — Deployment

> Target deploy & perintahnya. Untuk port/DB lihat `docs/PORTS.md`; untuk inventaris
> manifest lihat `docs/PROJECT_MAP.md`.

## 1. Target

| Target | Entry point |
|---|---|
| Dev (Docker) | `docker compose up --build` |
| Production (Docker) | `docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up -d` |
| Kubernetes | `kubectl apply -f k8s/` (db-secret → statefulset/service → domain-services → gateway → ingress) |

## 2. Artefak

| File | Peran |
|---|---|
| `docker-compose.yml` | Topologi dasar (dev + prod): postgres, 6 domain service, gateway, web |
| `docker-compose.override.yml` | Override dev (mount hot-reload `apps/`, `packages/`, `services/`; Postgres `127.0.0.1:15432`) — dimuat otomatis oleh `docker compose up` |
| `docker-compose.prod.yml` | Override produksi (`restart: always`, nginx 80/443, healthcheck gateway) |
| `docker-compose.registry.yml` | Varian image dari registry |
| `Dockerfile` | Image backend bersama — 2 stage (`python:3.12-slim` builder + runtime), `ARG SERVICE_CMD` |
| `k8s/` | Manifest K8s (gateway, domain-services, db-statefulset/service, ingress, hpa, alerting, loki/prometheus/jaeger, vault, redis, backup-cronjob) |
| `.env.prod.example` | Template env produksi |

Satu image backend melayani **semua** service Python; yang berbeda hanya
`command`/`SERVICE_CMD` per container.

## 3. Docker — Production

```bash
# sesuai header docker-compose.prod.yml:
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f gateway
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml down
```

Env produksi wajib (lihat `.env.prod.example`): `POSTGRES_PASSWORD`, `SECRET_KEY`;
opsional `GEMINI_API_KEY`, `NEXT_PUBLIC_SITE_URL`.

Topologi prod menambah **nginx** (`:80`/`:443`, config di `docker/nginx/nginx.conf`).
Gateway expose `8444`; web `3000`.

## 4. Kubernetes

- Ingress `finance-tracker-ingress` berhenti di Service `alpha-gateway` (host `quant.internal`).
- Sidecar **tailscale** berjalan hanya di gateway.
- Gateway Deployment `alpha-gateway` `replicas: 2`.

```bash
kubectl apply -f k8s/
```

## 5. Migrasi DB

Skema di-apply oleh runner migrasi (lihat `migrations/README.md` dan `DATABASE.md`):

```bash
python migrations/runner.py status   # Applied/Pending
python migrations/runner.py apply    # apply pending berurutan
python migrations/runner.py verify   # cek checksum migrasi yang sudah diterapkan
```

Pada Docker, `ALPHA_AUTO_MIGRATE=1` membuat tepat satu service apply migrasi saat boot
(advisory lock Postgres). `SchemaInitializer` juga memvalidasi skema saat startup.

## 6. Backup & recovery

Lihat `docs/infrastructure/BACKUP_STRATEGY.md`.

```bash
python scripts/tools/backup.py full                 # backup penuh (pg_dump -Fc)
python scripts/tools/backup.py list                 # daftar backup
python scripts/tools/backup.py verify               # verifikasi backup terakhir
python scripts/tools/backup.py restore <backup_file> # restore (interaktif, hati-hati)
```

Retensi default 30 hari (`BACKUP_RETENTION_DAYS`), direktori `./backups`
(`BACKUP_DIR`). K8s produksi: CronJob backup (lihat `k8s/backup-cronjob.yaml`).
**Restore menimpa DB saat ini — lakukan pre-restore backup dan uji restore di
non-produksi.**

## 7. Keamanan

- Jangan deploy dengan `SECRET_KEY` default (config gagal boot tanpa `SECRET_KEY`).
- CORS default hanya localhost; override via `FINANCE_TRACKER_CORS_ORIGINS`.
- Service internal (`8450–8455`) diasumsikan network-private; expose hanya gateway.
- Utang stage-1 + trigger review: `docs/maintenance/HONEY_DEBT.md`.

## Sumber

- `README.md` §Deployment, §Security Notes.
- `docker-compose.yml`, `docker-compose.override.yml`, `docker-compose.prod.yml`,
  `docker-compose.registry.yml`, `Dockerfile`.
- `k8s/` (`ingress.yaml`, `gateway.yaml`, `backup-cronjob.yaml`, …).
- `docs/infrastructure/BACKUP_STRATEGY.md`.
- `migrations/README.md`, `services/runtime/bootstrap.py` (`ALPHA_AUTO_MIGRATE`).
- `docs/PORTS.md`, `.env.prod.example`.
