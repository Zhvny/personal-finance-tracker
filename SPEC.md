# Alpha — Spec (Requirements & Contracts)

> Konsolidasi kebutuhan produk dan kontrak teknis dari sumber yang ada.
> **Bukan** inventaris area/status (itu di `docs/PROJECT_MAP.md`) dan **bukan** narasi
> cara sistem bekerja (itu di `ARCHITECTURE.md`/`DESIGN.md`).

## 1. Tujuan produk

Alpha adalah platform personal finance + investment intelligence **local-first**:
menggabungkan expense tracking, FIFO portfolio accounting, OCR receipt ingestion,
behavioral finance scoring, dan AI-assisted market analysis dalam satu stack
deployable. Runtime: microservice mesh Python/TypeScript di belakang gateway
FastAPI, dengan dashboard Next.js, GUI Electron, dan CLI TUI Textual.

Diferensiasi: arsitektur local-first, OCR ensemble dengan kategorisasi belajar,
akuntansi investasi FIFO, dan sistem market intelligence multi-agent yang
regime-aware. Sumber: `PRD.md` §1.

## 2. Status dokumen kebutuhan

| Dokumen | Standar | Isi saat ini |
|---|---|---|
| `PRD.md` (root) | — | **Kananonik** — kebutuhan produk, market, fitur |
| `docs/SRS.md` | ISO/IEC/IEEE 29148:2018 | Kerangka; sebagian besar bagian `TBD` |
| `docs/SDD.md` | ISO/IEC/IEEE 1016:2023 | Kerangka; sebagian besar `TBD` |
| `docs/SDP.md` | ISO/IEC/IEEE 12207 | Kerangka; sebagian besar `TBD` |
| `docs/TP.md` | IEEE 829 | Kerangka; sebagian besar `TBD` |
| `docs/UM.md` | ISO/IEC/IEEE 26514 | Kerangka; sebagian besar `TBD` |
| `docs/superpowers/specs/**` | — | Desain terverifikasi per-fitur (lihat §4) |
| `docs/features/*.md` | — | Spesifikasi fitur + workflow n8n |

Bagian `TBD` di dokumen ISO di atas **tidak** diisi di sini — dokumen itu yang harus
dilengkapi; `SPEC.md` hanya menautkan.

## 3. Kebutuhan fungsional (per domain)

Spesifikasi detail per fitur ada di `docs/features/`; kontrak per-service di
`services/<name>/docs/SPEC.md` (generated).

| Domain | Service | Spesifikasi |
|---|---|---|
| Expense tracking | `ledger` | `docs/features/expense-tracker.md` |
| Income tracking | `ledger` | `docs/features/income-tracker.md` |
| Investment (FIFO) | `portfolio` | `docs/features/investment-tracker.md` |
| Receipt OCR | `insights` | `docs/features/receipt-reader.md` |
| Behavioral finance | `engagement` | `docs/features/behavioral-finance.md` |
| AI advisor | `insights` | `docs/features/ai-financial-advisor.md` |
| Advanced analytics | `insights` | `docs/features/advanced-analytics.md` |
| Multi-profile switch | `platform` | `docs/features/multi-profile-switcher.md` |
| Stock/ML/genetic/senate | `market` | `docs/superpowers/specs/*` + `services/market/docs/SPEC.md` |

## 4. Kebutuhan non-fungsional (terverifikasi)

- **Isolasi per-profil (2026-09-18):** data finansial diisolasi per profil via
  Postgres schema-per-profile + `search_path`. Model Prisma **unqualified** (tanpa
  `multiSchema`/`@@schema`). Hanya data BARU yang terisolasi; data pra-isolasi tetap
  di schema shared `alpha_*` (orphaned by decision). Sumber: `docs/SCHEMA_AUTHORITY.md`,
  `docs/SRS.md` rev 1.1.
- **Auth seragam:** semua `/api/*` wajib `require_scope(...)`; hanya `/health*` publik
  (termasuk `/api/config` kini dilindungi). Sumber: `docs/SRS.md` rev 1.1, `AGENTS.md`.
- **Local-first:** penyimpanan utama Postgres lokal; tidak ada egress cloud wajib
  untuk operasi inti. Sumber: `PRD.md` §1.
- **Runtime:** Python `>=3.12,<3.13`; monorepo Turborepo + pnpm. Sumber: `pyproject.toml`.
- **Kualitas:** gate test coverage `fail_under=40`, lint `ruff check .`
  (line-length 120, py312) — detail di `TESTING.md`.

## 5. Kontrak per-service

Kontrak input/env, scope auth, dan mode error tiap service di-generate dari kode ke
`services/<name>/docs/SPEC.md`. Batas tanggung jawab (`purpose`/`owns`/`known_gaps`)
dari `docs/project.toml` blok `[service.*]`. Regenerate:
`python scripts/gen_service_docs.py`.

## 6. Spesifikasi sistem (arsip desain)

`docs/superpowers/specs/` memuat desain yang disetujui/terverifikasi, termasuk:

- `2026-10-12-repo-hygiene-design.md` — hygiene repo, map/status generated, karantina.
- `2026-09-16-fix-gateway-ip-whitelist.md`.
- `2026-05-25-infra-stability-design.md`, `2026-05-25-elite-system-audit-design.md`.
- `2025-09-16-automated-testing-design.md` (pipeline 3-layer, target).

## Sumber

- `PRD.md` (kebutuhan produk).
- `docs/SRS.md`, `docs/SDD.md`, `docs/SDP.md`, `docs/TP.md`, `docs/UM.md` (kerangka ISO).
- `docs/superpowers/specs/**` (desain sistem).
- `docs/features/*.md` (spesifikasi fitur).
- `docs/SCHEMA_AUTHORITY.md`, `docs/DATABASE_STRATEGY.md` (isolasi & persistensi).
- `docs/project.toml` (`[service.*]`), `services/*/docs/SPEC.md` (generated).
- `AGENTS.md`, `pyproject.toml`, `ruff.toml`.
