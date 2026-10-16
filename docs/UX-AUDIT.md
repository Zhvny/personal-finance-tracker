# UX Audit — Alpha (apps/web)

Tanggal: 2026-08-22 · Statis · Status lengkap di `../UX-AUDIT.md`

## Metrik

24 file tsx/ts · **60 kelas breakpoint** (sangat padat, disiplin) ·
6 tabel semua ber-wrapper overflow (9×) · 2 fixed-width minor.

## Temuan

| ID | Isi | Status |
|----|-----|--------|
| U-1 | 7× `h-screen` (lompatan address bar iOS Safari) | **FIXED** — semua diganti `h-dvh` |

## Sisa tindakan

- Dua `w-[≥100px]`: pastikan ada fallback responsif di container-nya.

---

## Audit Diperdalam (responsive + states + slop)

Tanggal: 2026-08-23 · Statis · Cakupan: `apps/web` (kanonik) + `apps/finance-tracker-gui`

### Klarifikasi cakupan & koreksi

- `apps/finance-tracker-gui` **deprecated resmi** — `DEPRECATED.md` menyatakan superseded oleh
  `apps/web` (keputusan 2026-08-11). Tidak diaudit penuh; sumber UI kanonik = `apps/web`.
- **Koreksi temuan lama**: "dua fixed-width" ternyata false positive regex —
  `analytics/page.tsx` yang terdeteksi `w-400`/`w-500` adalah kelas warna `text-yellow-400`/`yellow-500`
  (baris 153, 1059, 1125, 1149). Fixed-width nyata tinggal `min-w-[200px]` pada tombol
  (`business/page.tsx:415`, disengaja) dan `max-w-[160px] truncate` (`business/page.tsx:1204`, aman).

### Responsif — VERDICT: SEHAT

60 kelas breakpoint tersebar 11/12 file UI. Drawer sidebar mobile lengkap: overlay klik-tutup +
Escape + focus management (`sidebar.tsx:362-394`), skip-link (`layout-content.tsx:12-17`),
`min-h-dvh`/`lg:pl-72` (`layout-content.tsx:21`). Kedua tabel ber-wrapper `overflow-x-auto`
(`analytics/page.tsx:719, 1206`). Touch target nav ≈40px — sedikit di bawah 44px, wajar untuk
dashboard desktop-first, risiko rendah.

### States — ada lubang silent-error

Ada: `app/loading.tsx` + `app/analytics/loading.tsx`, skeleton di 5 file, error state sidebar
("API unavailable", `sidebar.tsx:505-513`), disabled-saat-proses (business ×6, import BOQ, modal profil).
GAP:

1. **Tidak ada `app/error.tsx`** sama sekali — crash render = layar putih dev-default.
2. **5 dari 6 halaman data menelan error fetch diam-diam** (analytics, overview, behavioral,
   logs, reward — nol referensi error UI). API mati → halaman menampilkan angka nol/kartu kosong
   seolah data valid. Kontrasnya `business/page.tsx` sudah benar (4 titik error UI) — tiru polanya.
3. Switch profil menelan kegagalan dengan `catch {}` tanpa feedback (`sidebar.tsx:82-83`).

### Slop Score: **22/100** (band ship-ok)

1. Objek domain dalam dan nyata: format `Rp … jt`, severity anomaly CRITICAL/HIGH/MEDIUM, komponen
   health-score berbobot, verdict lifestyle trend inflating/healthy/stable — bukan metrik filler.
2. Identitas visual disiplin: aksen berbasis `foreground`, bukan biru/ungu default; LiquidNav custom;
   bukan template SaaS yang bisa ditukar antar proyek.
3. Kelemahan generik tipis saja: kartu KPI recharts standar di analytics — isinya tetap spesifik produk.

### Rencana perbaikan terkecil

1. Tambah `app/error.tsx` (~15 baris) — tutup jalur crash-biasa-putih.
2. Banner error minimal di 5 halaman yang menelan fetch error (pola sudah ada di business).
3. Feedback inline/toast saat switch profil gagal (`sidebar.tsx:82`).
