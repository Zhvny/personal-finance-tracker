# Alpha — Database

> Narasi strategi persistence. Inventaris tabel/schema terperinci ada di
> `docs/DATABASE_STRATEGY.md` dan `docs/infrastructure/POSTGRES_MAPPING.md`;
> batas otoritas di `docs/SCHEMA_AUTHORITY.md`.

## 1. Ringkas

- **PostgreSQL = satu-satunya store kanonik** untuk data finansial, profil, dan sistem.
- **SQLite** hanya untuk fungsi lokal-spesifik: caching, audit lokal, snapshot
  behavioral, dan jalur impor legacy (read-only).
- Data finansial diisolasi **schema-per-profil** (`personal`, `business`, custom).

## 2. Otoritas skema

- Direktori **`migrations/`** = sumber otoritatif tunggal. Tiap migrasi = file `.sql`
  bernomor berurutan.
- `packages/api/backend/infrastructure/schemas.py` (`SchemaInitializer`) memverifikasi
  schema per-profil saat startup.
- `packages/core/infrastructure/persistence/per_profile_ddl.py`
  (`build_all_ddl_for_profile`) + `migrations/015_per_profile_schema.sql` menyediakan
  tabel lengkap tiap schema profil.
- `packages/database/schema.prisma` = model ORM. Sejak 2026-09-18 **tanpa**
  `multiSchema`/`@@schema`; tabel **unqualified** dan resolve ke schema profil aktif
  via `search_path={profile},public` (diset di `packages/database/index.py`).
- Jaga `schema.prisma` tetap kompatibel kolom dengan DDL per-profil (terutama `user_id`).
- `alpha_db_schema.sql` **Deprecated** — referensi historis; jangan diperbarui/sentuh.

## 3. Isolasi per-profil (2026-09-18)

- Tiap profil = schema Postgres sendiri; baca/tulis Prisma di-scope `search_path={profile},public`.
- Data finansial baru (income/expense/investments) terisolasi per profil.
- Schema shared lama `alpha_*` menyimpan data pra-isolasi (orphaned by decision —
  hanya data BARU yang diisolasi).
- Menambah field Prisma → mirror ke `per_profile_ddl.py` **DAN** ALTER schema profil
  existing (`ADD COLUMN IF NOT EXISTS ...`) atau buat migrasi.

## 4. Skema & tabel (high-level)

| Schema | Isi |
|---|---|
| `public` | `schema_migrations`, tabel N8N (`currency_history`, `asset_price_history`) |
| `system` | `profiles` (manajemen multi-profil) |
| `audit` | `audit_log` (pelacakan aksi) |
| `market` | `covariance_cache`, `market_data`, `ohlcv_cache`, dll. |
| `{profile}` | tabel finansial per profil: `expenses`, `incomes`, `investments`, `transactions`, `accounts`, `categories`, `budgets`, `goals`, … |

> `docs/infrastructure/POSTGRES_MAPPING.md` memetakan tabel SQLite lama ke schema
> Postgres terpadu (`core`, `investment`, `market`, `audit`) — sebagian bersifat
> rencana, bukan semua sudah diterapkan. _(belum diverifikasi per-tabel)_

## 5. Migrasi

Runner: `migrations/runner.py`, mencatat versi di `public.schema_migrations`.

```bash
python migrations/runner.py status
python migrations/runner.py apply
python migrations/runner.py verify
```

- Migrasi bersifat **aditif**. Rollback = tulis migrasi "forward" baru; jangan ubah
  `.sql` yang sudah diterapkan (merusak validasi checksum `runner.py verify`).
- `005_profile_schema_template.sql` **dilewati** runner — hanya dokumentasi schema
  yang di-instansiasi dinamis.
- Rentang saat ini: `001_schema_version_table.sql` … `019_add_user_id_budgets.sql`
  (termasuk `015_per_profile_schema.sql`, `016_service_schemas.sql`,
  `018_add_user_id_per_profile.sql`).

Menambah perubahan skema:
1. Tambah file bernomor baru di `migrations/`.
2. Perbarui `per_profile_ddl.py` + `SchemaInitializer` bila perlu DDL per-profil baru.
3. Mirror field Prisma baru ke DDL per-profil dan schema existing.
4. Jangan modifikasi `alpha_db_schema.sql`.

## 6. Backup & recovery

`pg_dump` (lihat `docs/infrastructure/BACKUP_STRATEGY.md`). Karena profil = schema,
DB bisa di-dump utuh atau per-schema.

```bash
python scripts/tools/backup.py full
python scripts/tools/backup.py restore <backup_file>   # menimpa DB — hati-hati
```

## 7. Catatan konteks

- `docs/system/database-schema.md` mendeskripsikan **arsitektur SQLite terdistribusi
  era CLI** — berguna untuk bentuk tabel domain, **bukan** strategi persistence saat ini.
- `docs/DATABASE_STRATEGY.md` memuat inventaris tabel/schema kanonik lengkap.

## Sumber

- `docs/DATABASE_STRATEGY.md`.
- `docs/SCHEMA_AUTHORITY.md`.
- `docs/system/database-schema.md` (konteks era CLI).
- `docs/infrastructure/POSTGRES_MAPPING.md`.
- `packages/database/schema.prisma`, `packages/database/index.py`.
- `migrations/README.md`, `migrations/` (001–019), `migrations/runner.py`.
- `packages/core/infrastructure/persistence/per_profile_ddl.py`,
  `packages/api/backend/infrastructure/schemas.py`.
- `docs/infrastructure/BACKUP_STRATEGY.md`, `scripts/tools/backup.py`.
