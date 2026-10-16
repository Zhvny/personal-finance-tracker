# 📋 QA Test Plan: Finance Tracker CLI (Exhaustive Edition)
**Versi:** 1.2  
**Target Aplikasi:** `apps/cli/main.py`  
**Metode Eksekusi:** Interactive Integer-Based Input & Automated Runner  
**Tujuan:** Memastikan integritas data, isolasi profil, fungsionalitas seluruh modul (A-K), keamanan siber, dan toleransi kesalahan (*fault tolerance*).  
**Terakhir Diperbarui:** 24-06-2026 (13:46)

---

## 1. Persiapan Lingkungan (Pre-Test)
- Pastikan lingkungan sandbox diaktifkan untuk mencegah modifikasi data riil:
  ```bash
  python tests/run_sandbox_cli.py --clean
  ```
- Pastikan folder sandbox `tests/sandbox_env/` memiliki izin baca/tulis.
- Pastikan koneksi internet tersedia untuk penarikan data harga saham real-time (yfinance).

---

## 2. Tabel Alur Pengujian (Test Flows)

### Flow A: Profiling & Isolasi (Profile Switcher)
| ID | Langkah | Input Integer | Hasil yang Diharapkan |
| :--- | :--- | :--- | :--- |
| A.1 | Switch ke Personal | `8` -> `1` | Dashboard menampilkan label "PERSONAL". |
| A.2 | Isi Data Dummy | `3` -> `1` -> `Tes` -> `5000` -> `y` | Saldo INC di Personal bertambah 5K. |
| A.3 | Switch ke Business | `8` -> `2` | Dashboard menampilkan label "BUSINESS". |
| A.4 | Verifikasi Isolasi | Lihat Dashboard | Saldo INC harus tetap 0 (Data Personal tidak bocor). |

### Flow B: Investasi (Buy, Hold, Sell FIFO)
| ID | Langkah | Input Integer | Hasil yang Diharapkan |
| :--- | :--- | :--- | :--- |
| B.1 | Beli Lot 1 | `1` -> `1` -> `AAPL` -> `us` -> `150` -> `10` -> `y` | Lot 1 tersimpan (10 unit @ 150). |
| B.2 | Beli Lot 2 | `1` -> `1` -> `AAPL` -> `us` -> `170` -> `10` -> `y` | Lot 2 tersimpan (10 unit @ 170). |
| B.3 | Cek Portofolio | `1` -> `3` | Total 20 unit AAPL muncul dengan harga real-time. |
| B.4 | Jual (FIFO) | `1` -> `7` -> `AAPL` -> `15` -> `200` | Lot 1 habis, Lot 2 sisa 5 unit. P/L dihitung benar. |
| B.5 | Realized P/L | `1` -> `8` | Menampilkan riwayat keuntungan dari 15 unit tadi. |

### Flow C: Pengeluaran & Budgeting
| ID | Langkah | Input Integer | Hasil yang Diharapkan |
| :--- | :--- | :--- | :--- |
| C.1 | Input Pengeluaran | `2` -> `1` -> `100` -> `Kopi` -> `1` -> `1` -> `y` | Teratat IDR 100 di kategori Food. |
| C.2 | Cek Summary | `2` -> `3` | Muncul tabel pengeluaran bulanan. |
| C.3 | Budget Check | `2` -> `5` | Progress bar budget muncul (Hijau/Merah). |

### Flow D: OCR & Integrasi (Scan Struk)
| ID | Langkah | Input Integer | Hasil yang Diharapkan |
| :--- | :--- | :--- | :--- |
| D.1 | Scan Struk | `4` -> `1` -> `tests/fixtures/receipt.jpg` | OCR mendeteksi Merchant, Tanggal, & Total. |
| D.2 | Koreksi Data | `y` (pada prompt edit) | User bisa mengubah angka hasil OCR jika salah. |
| D.3 | Export | `1` (Export to Expense) | Data otomatis terkirim ke modul Expense Tracker. |

### Flow E: Intelligence (ML Sniper & Butterfly)
| ID | Langkah | Input Integer | Hasil yang Diharapkan |
| :--- | :--- | :--- | :--- |
| E.1 | Sniper Advice | `1` -> `5` -> `BTCUSD` -> `crypto` | Muncul target price & skor konfiden dari ML. |
| E.2 | Agent Senate | `1` -> `10` -> `AAPL` -> `us` | Muncul voting Buy/Hold/Sell dari 3 sub-agent AI. |
| E.3 | Butterfly Map | `1` -> `11` -> `TSLA` -> `us` | Muncul korelasi risiko makro (DXY, Oil, dll). |

### Flow F: Stock Analyzer (Technical Analysis)
| ID | Langkah | Input Integer | Hasil yang Diharapkan |
| :--- | :--- | :--- | :--- |
| F.1 | Ticker Analysis | `5` -> `MSFT` | Muncul data fundamental (Expectancy, Kelly Criterion). |
| F.2 | Score View | `Score` | Muncul nilai kuantitatif untuk ticker tersebut. |

### Flow G: Predictive ML (Price Forecasting)
| ID | Langkah | Input Integer | Hasil yang Diharapkan |
| :--- | :--- | :--- | :--- |
| G.1 | Run ML Sniper | `6` | Aplikasi Sniper eksternal berjalan (Top Picks). |
| G.2 | Manual Predict | Masukkan `NVDA` | Muncul prediksi harga penutupan besok. |

### Flow H: Behavioral Finance & Business Reporting
| ID | Langkah | Input Integer | Hasil yang Diharapkan |
| :--- | :--- | :--- | :--- |
| H.1 | Personal Report | `7` (dalam Personal) | Muncul analisis psikologi belanja (Behavioral). |
| H.2 | Business Report | `7` (dalam Business) | Laporan P&L (Profit & Loss) Kuartalan disimpan. |

### Flow I: Whale Profiler (Volume Tracking)
| ID | Langkah | Input Integer | Hasil yang Diharapkan |
| :--- | :--- | :--- | :--- |
| I.1 | Track Whale | `9` -> `ETHUSD` -> `crypto` | Menampilkan deteksi volume besar (Whale movement). |

### Flow J: Income Management
| ID | Langkah | Input Integer | Hasil yang Diharapkan |
| :--- | :--- | :--- | :--- |
| J.1 | Manual Income | `3` -> `1` -> `5000` -> `Side Job` -> `y` | Pemasukan tercatat manual di database. |
| J.2 | View Income | `3` -> `2` | Muncul tabel histori pemasukan. |

### Flow K: Exit & Integrity
| ID | Langkah | Input Integer | Hasil yang Diharapkan |
| :--- | :--- | :--- | :--- |
| K.1 | Safe Exit | `0` | Aplikasi tertutup, koneksi DB diputus dengan aman. |
| K.2 | Verification | Cek file `.db` | Database tidak corrupt dan bisa dibuka kembali. |

---

## 3. Negative Testing (Stress Test)
Pastikan aplikasi **TIDAK CRASH** pada kondisi berikut:
1. **Input Huruf:** Masukkan `"abc"` pada menu yang meminta angka.
2. **Empty Input:** Langsung tekan `Enter` pada input "Amount".
3. **Invalid Path:** Masukkan path struk yang tidak ada (Flow D).
4. **Offline Mode:** Matikan internet lalu coba akses menu `5` atau `9`.

## 3.1 Cakupan Tambahan: Operasional dan Kompatibilitas

| Area | Skenario minimum | Kriteria lulus |
| :--- | :--- | :--- |
| Dependency / supply chain | Jalankan audit lockfile dan pemeriksaan secret/SBOM pada CI. | Kerentanan high/critical dan secret baru memblokir rilis. |
| Backup / restore | Backup database yang berisi transaksi representatif, restore ke database kosong, lalu bandingkan jumlah dan hash data. | Data, relasi, dan migrasi kembali konsisten; prosedur terdokumentasi. |
| Timezone / localization | Uji batas hari/bulan pada `Asia/Jakarta` dan UTC serta format `id-ID`. | Tidak ada transaksi bergeser tanggal atau nilai salah format. |
| Accessibility | Keyboard-only, fokus terlihat, label form, pembaca layar, dan kontras pada halaman utama. | Tidak ada blocker WCAG 2.2 AA pada alur kritis. |
| Browser compatibility | Smoke test Chromium, Firefox, dan WebKit untuk login, dashboard, input transaksi, dan rewards. | Alur kritis berfungsi tanpa error console. |
| Deployment / rollback | Upgrade pada salinan database, health-check, dan rollback versi aplikasi/migrasi yang kompatibel. | Rollback terverifikasi tanpa kehilangan data. |
| Disaster recovery | Simulasikan kehilangan instance dan restore backup ke lingkungan baru. | RTO/RPO aktual dicatat dan memenuhi target yang disepakati. |

---

## 4. Automation Snippet (Python)
Gunakan script ini untuk menjalankan Flow di atas secara otomatis:
```python
import subprocess
import os

def run_qa(scenario_name, inputs):
    print(f"Testing {scenario_name}...")
    env = os.environ.copy()
    env["FINANCE_ROOT_OVERRIDE"] = "./tests/sandbox_env"
    p = subprocess.Popen(['python', 'apps/cli/main.py'], 
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
    stdout, _ = p.communicate(input="\n".join(inputs) + "\n")
    print(f"Output for {scenario_name} captured successfully.")

# Contoh eksekusi Flow A & J (Profile & Income)
run_qa("Flow A+J", ["8", "1", "3", "1", "Gaji", "10000", "y", "0", "0"])
```

---

## 5. Rencana Pengujian Detail Terpersonalisasi (All Features)

### 5.1 Fitur Switcher Profil (Menu CLI > Option 8)
*   **Category-Partition (Input: Nama Profil):**
    *   *Partisi Valid:* Profil standar (`personal`, `business`), Profil kustom (`personal_2`, `test_profile`).
    *   *Partisi Invalid:* Karakter khusus (`prof@!`), spasi (`my business`), string kosong (`""`), SQL Injection payload (`personal'; DROP TABLE profiles;--`).
*   **Kasus Uji Detail:**
    *   **PRO-01 (Valid):** Ganti profil ke Business (`8` ➔ `1` ➔ `2`). Dashboard harus bergeser ke "BUSINESS OVERVIEW".
    *   **PRO-02 (Valid):** Buat profil baru (`8` ➔ `2` ➔ `crypto`). Profil terdaftar aman di registry `profiles.json`.
    *   **PRO-03 (Invalid):** Membuat nama profil ilegal (`8` ➔ `2` ➔ `prof-123!`). CLI menampilkan pesan error karakter ilegal.
    *   **PRO-04 (Keamanan):** SQL Injection (`8` ➔ `2` ➔ `'OR '1'='1`). Masukan dinetralkan tanpa merusak SQLite registry.
    *   **PRO-05 (Resiliensi):** Ganti profil cepat 50x secara berturut-turut. Sistem tidak boleh mengalami deadlock SQLite.

### 5.2 Modul Investasi Saham/Crypto FIFO (Menu CLI > Option 1)
*   **Category-Partition (Input: Ticker, Price, Qty):**
    *   *Ticker:* Valid (`AAPL`, `BTCUSD`), Invalid (`$$$`, String kosong).
    *   *Price:* Positif desimal (`150.25`), Negatif (`-10`), Nol (`0`), Non-numerik (`"seratus"`).
    *   *Qty:* Positif integer (`10`), Negatif (`-1`), Nol (`0`), Desimal (`0.5` untuk crypto).
*   **Kasus Uji Detail:**
    *   **INV-01 (Valid):** Beli Lot 1 AAPL 10 unit @ $150. Lot tercatat di database portofolio dengan status `holding`.
    *   **INV-02 (Valid):** Beli Lot 2 AAPL 10 unit @ $170. Lot tercatat terpisah dengan ID lot baru.
    *   **INV-03 (Valid - FIFO):** Jual 12 unit AAPL @ $180. Lot 1 (10 unit) harus berstatus `sold`. Lot 2 (10 unit) terpotong 2 unit dan berstatus `partial_sold`. Keuntungan terealisasi dihitung tepat: +$320.
    *   **INV-04 (Invalid):** Jual 100 unit AAPL @ $180. Transaksi ditolak dengan pesan saldo unit tidak mencukupi.
    *   **INV-05 (Resiliensi):** Buka portofolio saat offline. Tampilan harus memuat data dari cache lokal `price_snapshots` tanpa memicu crash program.

### 5.3 Modul Pengeluaran & Anggaran (Menu CLI > Option 2)
*   **Category-Partition (Input: Amount, Category, Payment):**
    *   *Amount:* Positif desimal (`50000.50`), Negatif (`-2000`), Nol (`0`).
    *   *Category:* Terdaftar (`food`, `transport`), Tidak terdaftar (`holiday`).
    *   *Payment:* Terdaftar (`cash`, `credit_card`), Tidak terdaftar (`bitcoin`).
*   **Kasus Uji Detail:**
    *   **EXP-01 (Valid):** Belanja Rp75.000 kopi di kategori `food` via `cash`. Saldo pengeluaran dan limit bulanan terhitung proporsional.
    *   **EXP-02 (Valid):** Catat pengeluaran Rp5M pada kategori `food`. Indikator budget di CLI berubah menjadi merah.
    *   **EXP-03 (Invalid):** Nominal desimal desimal alfabet (`"gratis"`). Masukan ditolak secara elegan.
    *   **EXP-04 (Keamanan):** Detail transaksi diisi sql injection (`item'); DROP TABLE expenses;--`). Detail tersimpan sebagai string aman tanpa dieksekusi.

### 5.4 Pelacak Pemasukan & PPh 21 (Menu CLI > Option 3)
*   **Category-Partition (Input: Amount, Status Pernikahan):**
    *   *Amount:* Angka positif (`10000000`), Negatif (`-5000`), Nol.
    *   *Status Pajak (PTKP):* `TK/0` (Rp58.5jt), `K/0` (Rp63jt), `K/1` (Rp67.5jt), dll.
*   **Kasus Uji Detail:**
    *   **INC-01 (Valid):** Masukkan pemasukan Rp10.000.000 kategori `salary`. Pemasukan tersimpan di `income.db`.
    *   **INC-02 (Valid):** Pajak Bracket 5% (gaji 7.5jt/bln, TK/0). Total PPh 21 tahunan dihitung tepat Rp1.575.000.
    *   **INC-03 (Valid):** Pajak progresif gaji besar (PKP 600M). PPh 21 dihitung proporsional dengan bracket 5%, 15%, 25%, 30%, dan 35% secara presisi.
    *   **INC-04 (Invalid):** Gaji nominal negatif (`-5000000`). Input ditolak dan diminta input ulang.

### 5.5 Pembaca Kuitansi OCR Ensemble (Menu CLI > Option 4)
*   **Category-Partition (Input: Path Berkas Gambar):**
    *   *Path:* File gambar valid (`.jpg`, `.png` di direktori proyek), File non-gambar (`.txt`), File fiktif (`none.png`).
*   **Kasus Uji Detail:**
    *   **OCR-01 (Valid):** Pindai `tests/fixtures/receipt.jpg`. Data terdeteksi otomatis (Merchant, Tanggal, & Total).
    *   **OCR-02 (Invalid):** Gambar tidak ada (`tests/fixtures/hantu.jpg`). Ditangani secara aman dengan menampilkan pesan ramah.
    *   **OCR-03 (Valid):** Edit data manual (koreksi nominal ke `85000` sebelum diekspor). Data ter-override dan tersimpan aman di database.
    *   **OCR-04 (Keamanan):** Path Traversal (`../../../../windows/win.ini`). Input ditolak karena di luar direktori proyek.
    *   **OCR-05 (Resiliensi):** Pustaka EasyOCR/PaddleOCR rusak. Sistem otomatis mendowngrade engine ke Tesseract.

### 5.6 Analisis Saham Fundamental (Menu CLI > Option 5 - Personal Only)
*   **Kasus Uji Detail:**
    *   **STX-01 (Valid):** Analisis `MSFT`. Menampilkan Win Rate, Expectancy Index, Kelly %, dan fundamental rasio.
    *   **STX-02 (Invalid):** Ticker fiktif (`APLLEXYZ`). Sistem menampilkan peringatan data ticker tidak ditemukan.
    *   **STX-03 (Resiliensi):** API rate limit Yahoo Finance (HTTP 429). Program mendeteksi status limit, mengaktifkan backoff, dan menyajikan data dari snapshot lokal.

### 5.7 Prediksi Harga Berbasis ML Sniper (Menu CLI > Option 6 - Personal Only)
*   **Kasus Uji Detail:**
    *   **ML-01 (Valid):** Prediksi `NVDA`. Menampilkan perkiraan harga penutupan esok hari beserta Confidence Level (%).
    *   **ML-02 (Invalid):** Prediksi saham baru listing (IPO). Sistem menolak karena data historis untuk pelatihan model tidak memenuhi kuota minimal.

### 5.8 Laporan Behavioral Finance (Menu CLI > Option 7 - Personal Only)
*   **Kasus Uji Detail:**
    *   **BEH-01 (Valid):** Masukkan 5 transaksi `shopping` non-anggaran. Nilai Impulse Score di menu `7` meningkat menjadi "High Risk".
    *   **BEH-02 (Resiliensi):** Jalankan laporan saat database `behavioral.db` kosong. Sistem memberikan anjuran pencatatan awal tanpa crash.

### 5.9 Whale Volume Profiler (Menu CLI > Option 9 - Personal Only)
*   **Kasus Uji Detail:**
    *   **WHL-01 (Valid):** Track `ETHUSD`. Menampilkan chart volume horizontal dan mendeteksi anomali transaksi volume besar.
    *   **WHL-02 (Resiliensi):** Volume transaksi 0. Sistem memberikan fallback VWAP = Harga Terakhir untuk mencegah pembagian dengan nol (*division by zero*).

### 5.10 Laporan Keuangan Kuartalan (Menu CLI > Option 7 - Business Only)
*   **Kasus Uji Detail:**
    *   **REP-01 (Valid):** Buka menu `7` di profil Business. Laporan P&L kuartalan terbuat dan disimpan di direktori laporan.
    *   **REP-02 (Resiliensi):** Folder output dikunci (tidak ada izin tulis). Laporan dialihkan penyimpanannya ke folder `%TEMP%` dengan notifikasi.

### 5.11 Otomasi Daemon Scheduler (`apps/cli/scheduler.py`)
*   **Kasus Uji Detail:**
    *   **SCH-01 (Valid):** Jalankan scheduler daemon (`python apps/cli/scheduler.py start`). Sistem berjalan di latar belakang dan membuat berkas `scheduler.pid`.
    *   **SCH-02 (Safety):** Jalankan perintah `start` ulang. Ditangguhkan karena scheduler mendeteksi PID yang aktif.
    *   **SCH-03 (Resiliensi):** Isi `scheduler.pid` dirusak dengan PID acak. Scheduler melakukan deteksi kegagalan, menghapus PID lama, dan melakukan start ulang secara otomatis.
