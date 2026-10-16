# Catatan Ekosistem 2026-08-22

(diarsipkan dari root CHANGELOG.md)

### Alpha
- Konversi ke **microservice topology**: gateway :8444 + platform/ledger/portfolio/
  market/insights/engagement (:8450â€“8455), shared runtime bootstrap, OpenAPI-driven
  routing; legacy monolith deprecated tapi jalan.
- Scheduler advisory-lock (anti double-run saat transisi), healthchecks semua service,
  tech-debt ledger `docs/maintenance/HONEY_DEBT.md`.
- Compose dev/prod + k8s per-service + ingressâ†’gateway; runner `run-services.bat`.
- README didetailkan ulang (arsitektur/ports/env/deploy/docs map).

