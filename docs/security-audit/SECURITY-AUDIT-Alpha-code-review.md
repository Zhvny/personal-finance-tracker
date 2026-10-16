# Code Security Review — Alpha

Tanggal: 2026-08-22 · Metodologi: skill `code-review-security` (OWASP Top 10 + ASVS,
review line-level) · Cakupan: `packages/api/backend/**`, `services/**`, `apps/api/**`.
Skala: 🟠 TINGGI · 🟡 SEDANG · 🔵 RENDAH

## Lingkup

Trust boundary server-side penuh (data finansial + PII); framework FastAPI +
SQLAlchemy/psycopg2 + SQLite audit store; exposure internet via gateway :8444.

## Temuan

### CR-1 ✅ FIXED `7f29bf5` — Detail 502 membocorkan host internal downstream
`services/gateway/main.py:194` — `"detail": f"Upstream error: {e}"` menyertakan
`target_base` (mis. `http://platform:8450`) dalam respons ke klien anonim.
→ Sekarang detail generik ("Upstream unavailable."); error lengkap hanya di log.

### CR-2 ❌ FALSE POSITIVE — dikoreksi saat verifikasi
Kedua situs unggahan (receipts.py, ai.py) ternyata SUDAH memiliki whitelist
MIME + whitelist ekstensi (`_ALLOWED_EXT`) + cap 10MB dengan penolakan 400/413.
Tidak perlu perbaikan; laporan awal keliru karena hanya grep tanpa baca konteks.

### CR-3 ✅ FIXED `7f29bf5` — Log injection (kosmetik)
Path disanitasi (`\n`/`\r` → spasi) di log warning gateway dan debug log
middleware securty.

### CR-4 ✅ FIXED `7f29bf5` — `shell=True` dihapus
Argumen konstanta list cukup tanpa shell.

### CR-5 ✅ FIXED `416268f` — Scope admin kini hidup
`/api/admin/audit` (platform service) menuntut `require_scope("admin")`
dan mengekspos query_audit_log.

## Positif

- Semua pembandingan kredensial memakai `hmac.compare_digest`.
- Token sesi: `secrets.token_urlsafe(32)` (256-bit), disimpan sebagai SHA-256,
  TTL 12 jam, gagal-closed saat session store mati.
- Nol hardcoded secret di backend/services (sweep case-insensitive).
- Nol `$queryRawUnsafe`-setara: identifier SQL teregex, query data parameterized.
- `password_hash` hanya menyentuh DDL/insert/verify — tidak pernah diserialisasi
  ke response.

## Rekap severity

| Severity | Jumlah |
|---|---|
| 🟠 TINGGI | 0 |
| 🟡 SEDANG | 1 (CR-1) |
| 🔵 RENDAH | 4 (CR-2..CR-5) |
