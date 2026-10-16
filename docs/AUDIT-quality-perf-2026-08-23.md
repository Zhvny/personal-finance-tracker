# QUALITY-PERF AUDIT 2026-08-23 — Alpha
- **Duplikasi forking utuh**: `apps/cli/receipt_reader/core/engines/gemini_engine.py` ≡ `packages/core/application/receipt_reader/engines/gemini_engine.py` (identik byte-per-byte); `parser.py` dua versi 1187 vs 1290 baris saling drift.
- **Legacy hidup ganda**: `run.bat:148,232` masih mengeksekusi `packages/api/api_server.py` — HONEY_DEBT #6 **[KNOWN]**, diverifikasi masih aktif hari ini.
- **Lint gate merah**: `ruff check .` = 7.352 error (config sendiri: E,F,W,I @120). Terbesar: W293 3.049, F401 939, I001 709. ~5.278 auto-fixable.
- **Regresi test**: full-run 2026-08-23 → gagal `test_cli_driver::test_send_command`, `test_flow_a_isolation`, `test_flow_b_investment`, `test_flow_d_ocr_integration`, `flow_j::test_income_and_saving`, `test_database_manager_execute_rollback` + ERROR `test_flow_a::test_profile_isolation`. STATE.md hanya mencatat 1 flaky → perlu triase (regresi atau env-dependent).
- **God files**: `apps/web/src/app/business/page.tsx` (1385), `analytics/page.tsx` (1301), `packages/api/backend/routers/ai.py` (1103, 4 fungsi >80 baris), `ledger_engine.py` (1090), `ai_rule_engine.py` (1088).
- **Cache tanpa evict**: `_ANALYTICS_CACHE` (`routers/analytics.py:41-53`) entry expired tidak dibuang; `_BEHAVIORAL_CACHE` (`routers/deps.py:175-182`) satu timestamp global untuk semua key + tanpa evict.
- **N+1**: `recurring_service.py:240-261` INSERT per kandidat (pakai `executemany`); `postgres_expense_repository.py:109-124` SELECT dedup + INSERT per template dalam satu transaksi.


## Matriks Project × Dimensi

| Dimensi | Alpha | Beta | Gamma | Delta | Epsilon | Eta |
|---|---|---|---|---|---|---|
| **Duplikasi & dead code** | 🔴 fork `receipt_reader` utuh (1 file identik byte-per-byte); web ganda legacy+Next; F401=939 | 🟡 blok create-loop terduplikasi dalam `boq.ts`; `canPayout` tak terpakai | 🟡 6 unused vars (payroll P8 parsial); pola sync vs purchase mirip | 🟢 ringan (`canPayout`, 2×`<img>`) | 🟡 F401=11 | 🔴 tanpa eslint → dead code tak terdeteksi |
| **Kompleksitas** | 🔴 60+ fungsi >80 baris; 9 file >1000 baris | 🟡 `boq-tab.tsx` 964 baris | 🟡 `pos/page.tsx` 714 | 🟡 `dashboard/page.tsx` 458 | 🟡 4 fungsi >80 baris | 🔴 `services/api/src/index.ts` 1103 baris = seluruh API |
| **Konsistensi gaya (lint)** | 🔴 ruff **7.352 error** (gate resmi merah); Epsilon-style ruff beda filosofi | 🟢 eslint 0/0, tsc 0 | 🟢 eslint 0 err/6 warn, tsc 0 | 🟢 eslint 0 err/3 warn, tsc 0 | 🟡 ruff 162 err (B008=75 idiom FastAPI tanpa exemption) | 🔴 eslint tidak ada; worker tanpa typecheck script |
| **Test coverage** | 🔴 746✓/**6 FAIL**/1 error (10m); gate cuma 40% | 🟡 vitest 100/100 ✓ tapi **threshold coverage tak diset** (klaim gate ≥80 tidak enforce) | 🟢 77/77 ✓, gate 80/70 enforced | 🟢 152/152 ✓, 93.79%/89.47% (STATE "63/63" stale) | 🟢 pytest 116/116 ✓ (21s) | 🔴 hanya 2 test file di `packages/shared`; api/gateway/worker **zero test** |
| **Query lambat / N+1** | 🔴 INSERT-per-row `recurring_service.py:240`; SELECT+INSERT per template `postgres_expense_repository.py:109` | 🟠 update per ancestor tanpa batch `boq.ts:494`; rollup O(n²) `boq.ts:462` | 🟢 server batch insert ✓; loop client Dexie by-design | 🔴 cron billing: 3–4 query per langganan (`route.ts:43,49,94`) | 🟠 per-invoice SUM ×2 `jobs.py:289`; per-kontrak query `jobs.py:107`; N+1 `payouts.py:65` | 🟠 `nextNumber()` count()+1 racy `index.ts:196`; loop per template `index.ts:798` |
| **Memory leak proxies** | 🔴 `_BEHAVIORAL_CACHE` + `_ANALYTICS_CACHE` tanpa evict (tumbuh tak terbatas); timestamp TTL global salah desain | 🟠 rate-limit Map tanpa evict (Gamma/Delta sudah fix, Beta belum) | 🟢 rate-limit ada MAX_BUCKETS evict ✓; sync engine cleanup benar | 🟢 evict ada ✓ | 🟠 `_HITS` dict key tak pernah dihapus [KNOWN-risk] | 🟢 Redis TTL di semua cache ✓ |
| **Caching strategy** | 🟡 banyak cache in-process TTL bervariasi (300s–3600s), invalidasi manual via `_bust_*` tersebar di 10+ router | 🟢 none server-side (React Query saja — sesuai skala) | 🟢 SW workbox (api excluded), Dexie local-first, purge saat sign-out ✓ | 🟢 React Query; no server cache | 🟢 none (DB langsung, fine untuk manager-only) | 🟢 gateway Redis 30s TTL + circuit breaker ✓; result hash TTL 24h ✓ |
| **Skalabilitas (singleton in-process)** | 🔴 sqlite auth/audit (`security/core.py:87`), scheduler in-proc + backoff in-memory, `market_sync_backoff.json`, telegram poll in-proc — semua break multi-instance [KNOWN #1/#7 berkaitan] | 🟠 rate-limit in-memory [KNOWN]; upload filesystem ephemeral [KNOWN] | 🟢 backendless Supabase/PG ✓ | 🟠 rate-limit in-memory [KNOWN] | 🟠 APScheduler in-proc, denylist JWT in-mem [KNOWN AGENTS.md] | 🟢 BullMQ + Redis queue ✓ arsitektur paling siap scale |

Legend: 🟢 sehat · 🟡 perlu perhatikan · 🟠 utang nyata · 🔴 prioritas.

---

## Quick Wins (urut dampak/biaya)

1. **Delta — de-N+1 cron billing**: hoist `platformConfig.upsert` keluar loop, ganti per-sub `count`/`findFirst` dengan 2 query `groupBy(subscriptionId)`, kumpulkan update lalu `$transaction` batch. Menghapus ~4 round-trip per langganan; file tunggal, tanpa perubahan perilaku.
2. **Alpha — pulihkan gate lint**: `ruff check . --fix` (~5.278 error fixable otomatis: W293/F401/I001/E501-sebagian), sisakan F821/F811 untuk triase manual. Gate resmi kembali hijau; 939 unused-import = dead code terbuang gratis.
3. **Beta — satukan blok BOQ + batch rollup**: ekstrak helper `createItems(tx, projectId, rows)` dari duplikat importRows/applyTemplate, bungkus loop update `recomputeAncestors` dalam `$transaction`, tambah `thresholds` di vitest config agar gate 80/70 nyata. Sekalian pecah `boq-tab.tsx` jadi 4 file komponen.
4. **Eta — infrastruktur QA minimum**: tambah eslint + script typecheck di worker, pecah `services/api/src/index.ts` per modul rute, ganti `nextNumber()` dengan sequence/tabel counter atomic, dan minimal 1 test untuk alur transisi PR→PO (state machine + race nomor dokumen = risiko data korup paling tinggi).
5. **Epsilon — rapikan worker & lint**: batch `recalc_totals` jadi 2 query GROUP BY, hapus N+1 `payouts.py:65` (eager-load owner), tambah eviction `_HITS`, import `Session` di `templates.py`, dan exemption B008 untuk FastAPI `Depends`.

Bonus murah: triase 6 kegagalan test Alpha (bisa regresi nyata); hapus 9 unused vars/import Gamma-Delta; samarkan drift CSP Beta/Eta-web dengan menyalin blok header Gamma.
