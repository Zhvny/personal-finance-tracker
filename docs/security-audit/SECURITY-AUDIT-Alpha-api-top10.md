# API Security Review — Alpha · OWASP API Security Top 10 (2023)

Tanggal: 2026-08-22 · Metodologi: skill `api-security-review` ·
Permukaan: gateway :8444 (exact-route dari OpenAPI) → 6 services + legacy monolit.
Skala: 🟠 TINGGI · 🟡 SEDANG · 🔵 RENDAH

## 1. Inventaris permukaan & mekanisme auth

| Aspek | Nilai |
|---|---|
| Endpoint | exact-route table dari `/openapi.json` tiap service (auto-discovery, anti route-drift) |
| AuthN | Bearer: master API key (env) **atau** session `user_*` 12 jam |
| AuthZ | scope read<write<admin, fail-closed, dideklarasikan per-router/endpoint |
| Gateway | pure router; auth dipaksakan di service layer; hop-by-hop stripped |

## 2. Matriks OWASP API Top 10

| Kat | Risiko | Status | Ringkas |
|---|---|---|---|
| API1 | BOLA | 🟢 desain / 🔵 catatan | Single-manager: objek tidak di-scope per-user; token register = read-only |
| API2 | Broken Authentication | ✅ FIXED `416268f` | Dual-key rotation grace; sesi 12 jam ✓; brute-force dibatasi rate limit |
| API3 | BOPLA (Mass Assignment) | 🟢 | Nol `extra="allow"`; pydantic v2 default ignore-extra; tulisan kolom eksplisit |
| API4 | Resource Consumption | 🟢 / 🔵 | Rate limit global + pagination cap (ledger ≤500, audit ≤1000); AI/ML compute berat di belakang write-scope |
| API5 | BFLA | ✅ FIXED `416268f` | Tier admin kini hidup: `/api/admin/audit` (`require_scope("admin")`) mengekspos query_audit_log via platform service |
| API6 | Unsafe Business Flows | 🟢 | Scheduler dilindungi advisory lock + write-scope |
| API7 | SSRF | 🟢 | Target proxy env-only; tidak ada endpoint fetch URL user |
| API8 | Misconfiguration | 🟢 / ✅ | CORS allowlist, header lengkap; CR-1 detail 502 ✅ FIXED `7f29bf5` |
| API9 | Inventory | 🟡 | Legacy monolit masih hidup = permukaan ganda; gateway auto-discovery menjaga paritas rute |
| API10 | Unsafe Consumption | 🟢 | Payload eksternal JSON-parsed saja; nol pickle/yaml unsafe |

## 3. Temuan detail & skenario serangan

### A-API2 ✅ FIXED `416268f` — Kredensial utama statis tanpa rotasi
Kini mendukung **jendela rotasi dual-key**: set `FINANCE_TRACKER_API_KEY`
(baru) + `FINANCE_TRACKER_API_KEY_PREVIOUS` (lama) — keduanya diterima selama
grace period (`core.py::_key_matches`, compare_digest). HMAC tetap diverifikasi
terhadap key aktif.

### A-API1 ✅ FIXED `416268f` — Register publik = baca seluruh data finansial
`/auth/register` kini **403 saat ENVIRONMENT=production** — registrasi hanya
terbuka di dev. Untuk tool personal, ini menutup vektor baca-penuh oleh
akun anonim yang menumpang.

### A-API4 🔵 Endpoint komputasi berat
Receipt OCR/AI parse (`write` scope) menjalankan model — satu token write bisa
menahan worker. Rate limit 300/menit membantu, tapi antrian/timeout eksplisit
per-job lebih tahan banting.

## 4. Skenario serangan yang sudah tertutup

1. Brute-force token → rate limiter sliding-window + compare_digest.
2. Route enumeration → 404 tanpa `known_roots` (F-2 FIXED).
3. Tampering mutasi in-transit → HMAC-SHA256 wajib di production.
4. Scheduler double-run → advisory lock + lease (TD-1).
5. Webhook palsu → kontrak verify-signature/amount-from-DB (pola Delta/Epsilon).

## 5. Roadmap

| # | Item | Status |
|---|------|--------|
| 1 | A-API2 kebijakan rotasi master key | ✅ dual-key grace `416268f` |
| 2 | A-API1 tutup register di production | ✅ `416268f` |
| 3 | API5 hidupkan tier admin untuk endpoint audit-query | ✅ `416268f` |
| 4 | A-API4 queue/timeout job AI | OPEN (sedang) |
