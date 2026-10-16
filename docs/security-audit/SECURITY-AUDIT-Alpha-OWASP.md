# Security Audit — Alpha · OWASP Top 10 Web Review

Tanggal: 2026-08-22 · Metodologi: skill `web-security-review` (OWASP Top 10 2021 + ASVS ringkas)
Cakupan: gateway :8444 + 6 domain services :8450–8455 + legacy monolit `apps/api` + routers library.
Skala: 🟠 TINGGI · 🟡 SEDANG · 🔵 RENDAH · ✅ KEBIJAKAN BAIK

## 1. Pemetaan Aplikasi

| Aspek | Nilai |
|---|---|
| Framework | FastAPI (services + legacy), React web |
| Deployment | docker-compose dev/prod, k8s/, lokal via run-services.bat; rencana VPS: HQ247-PLAN |
| Batas kepercayaan | internet → gateway → internal services; Telegram poll; upstream eksternal (yfinance, Gemini AI, Ollama) |
| Sensitivitas data | transaksi finansial, PII (email), struk OCR |
| Autentikasi | Bearer master API key (`FINANCE_TRACKER_API_KEY`) **atau** session token `user_*` (hash SHA-256 di SQLite, TTL); scope read<write<admin; DEV bypass loopback-only dan diabaikan saat ENVIRONMENT=production |

## 2. Matriks Risiko OWASP Top 10

| Kat | Risiko | Status | Ringkas |
|---|---|---|---|
| A01 | Broken Access Control | 🟢 kuat / 🟡 1 verifikasi | Scope hierarchy fail-closed di 39 router; WS proxy tanpa auth gateway (F-1) |
| A02 | Cryptographic Failures | 🟢 | HMAC compare_digest; PBKDF2-100k+salt; SECRET_KEY guard prod |
| A03 | Injection | 🟢 | Interpolasi identifier SQL teregex ketat; subprocess argv-list; React escape |
| A04 | Insecure Design | 🟢 | TD-1 scheduler ownership terkunci; kontrak webhook terdokumentasi |
| A05 | Security Misconfiguration | 🟡 1 temuan | Header keamanan lengkap; DEBUG off default; F-4 HOST gateway inkonsisten |
| A06 | Vulnerable Components | 🟢 | Pin masuk akal; sarankan audit dependensi otomatis |
| A07 | Identification & Auth Failures | 🟢 / 🔵 | PBKDF2+salt, sesi hashed+TTL, rate limit; kebijakan password minim |
| A08 | Software & Data Integrity | 🟢 | Nol pickle/yaml.load/eval; JSON saja |
| A09 | Logging & Monitoring | 💪 SANGAT KUAT | audit_log per-request never-fail; X-Request-ID end-to-end |
| A10 | SSRF | 🟢 | Target proxy env-only; tidak ada fetch URL dari input user |

## 3. Temuan Detail

### F-1 🟡 WebSocket proxy tanpa autentikasi gateway (A01/A04)
`gateway/main.py:115` meneruskan `/ws/*` apa adanya ke platform :8450 **tanpa**
mengecek kredensial di hop pertama. Keamanan bergantung penuh pada handshake
protokol WS milik platform — yang belum diverifikasi.
→ **Verifikasi**: hubungkan WS tanpa token; kalau diterima, tambahkan cek token
di handshake gateway (query param/header) atau paksa platform menolak anonim.

### F-2 🔵 404 membocorkan struktur rute internal (A01)
`gateway/main.py:173-176` menyertakan `known_roots` di body 404 — pemetaan
topologi API untuk penyerang anonim.
→ Hapus field, atau dokumentasikan sebagai trade-off debugging.

### F-3 🔵 `/health` memaparkan matriks kesehatan downstream (A01)
Status tiap service internal terlihat anonim dari :8444.
→ Gerbang Caddy/k8s: batasi `/health` ke jaringan internal/monitoring.

### F-4 🟡 Default HOST gateway `0.0.0.0` (A05)
`gateway/main.py:210` membaca env langsung dengan fallback `"0.0.0.0"` — tidak
ikut perbaikan S-3 (default `127.0.0.1` di config.py). Mode lokal non-docker
kembali ekspos :8444 ke LAN.
→ Selaraskan fallback ke `127.0.0.1`; compose tetap setel eksplisit `0.0.0.0`.

### A02-1 🔵 HSTS ditangguhkan untuk HTTP lokal
Sengaja (komentar di core.py). Saat prod: pastikan TLS terminate di Caddy/k8s
ingress DAN HSTS aktif di lapisan itu (HQ247 Fase 3).

### A03-1 🔵 Identifier SQL tanpa quoting (defense-in-depth)
Dua situs interpolasi sudah teregex ketat (`^[a-z0-9_]{1,32}$`). Tambahkan
quoting `"{name}"` agar aman juga bila regex sengaja dilonggarkan nanti.
`apps/cli/scheduler.py:52` memakai `shell=True` tapi argumen konstanta — bukan
injection, hanya gaya; rapikan sewaktu disentuh.

### A07-1 🔵 Kebijakan password minimum
Min 8 char tanpa cek kompleksitas/breach; hashing PBKDF2-100k+salt sudah benar.
Pertimbangkan argon2id (paritas Epsilon) + cek breach saat register publik.

## 4. Kebijakan baik yang layak dipertahankan

- Session token disimpan **sebagai hash**, expiry dicek server-side, gagal-closed
  saat store tidak tersedia (`core.py:334-337`).
- Self-registration dikunci scope `read` — akun publik tak bisa menyentuh
  endpoint finansial tulis (`_token_scope`, ada komentar SECURITY eksplisit).
- Dev-mode auth bypass: loopback-only **dan** diabaikan saat production
  (`core.py:90-97`, `281-287`).
- HMAC-SHA256 wajib untuk mutasi di production + `compare_digest`.
- Audit log never-fail + header keamanan lengkap (nosniff, frame-deny,
  CSP `default-src none`, no-store untuk API finansial, Server dimask).
- Rate limiter sliding-window per-IP dengan limit lebih longgar untuk loopback.
- Guard startup menolak `SECRET_KEY` default saat production.

## 5. Roadmap prioritas

| # | Item | Status |
|---|------|--------|
| 1 | F-1 verifikasi/kunci auth WS | OPEN — verifikasi handshake platform |
| 2 | F-4 selaraskan HOST gateway | ✅ FIXED `e48d3c3` |
| 3 | F-2 sembunyikan known_roots | ✅ FIXED `e48d3c3` |
| 4 | A03-1 quoting identifier | OPEN 🔵 |
| 5 | A07-1 kebijakan password + argon2id | OPEN 🔵 |
| 6 | Deploy-time (HQ247): TLS/HSTS ingress, ALLOWED_IP_WHITELIST eksplisit, CI `pip-audit`+`pnpm audit` | menyusul fase |

### Remediasi tambahan dari audit kembar (lihat file code-review & api-top10)

CR-1/CR-3/CR-4 ✅ `7f29bf5` · CR-5/API5 ✅ · A-API1 ✅ · A-API2 ✅ (`416268f`) ·
CR-2 ❌ false positive (sudah hardened sejak awal).
