# Architecture Documentation
## Stock Machine Learning — Sniper Signal System v2.1 (Braver Edition)

> **Versi Dokumen:** 2.1  
> **Tanggal:** April 2026  
> **Perubahan dari v2.0:** Memperkenalkan **"Braver Sniper"** logic. Zona Neutral diperkecil secara drastis (**0.1x ATR**) untuk meningkatkan agresivitas sinyal tanpa mengorbankan integritas data. Threshold Sniper dikunci pada **≥0.90** untuk menjamin presisi 90% (DNA Gacor). Fitur diperluas menjadi 27 indikator microstructure lengkap.

---

## Daftar Isi

1. [Gambaran Umum Sistem](#1-gambaran-umum-sistem)
2. [Perubahan Utama v2.1 (Braver Edition)](#2-perubahan-utama-v21)
3. [Prinsip Desain](#3-prinsip-desain)
4. [Ticker Universe (list.txt)](#4-ticker-universe-listtxt)
5. [Struktur Direktori](#5-struktur-direktori)
6. [Layer Arsitektur](#6-layer-arsitektur)
7. [Pipeline Data: Akuisisi](#7-pipeline-data-akuisisi)
8. [Pipeline Data: Feature Engineering](#8-pipeline-data-feature-engineering)
9. [Triple Barrier Labeling: Thin Neutral Zone](#9-triple-barrier-labeling-thin-neutral-zone)
10. [Model Training: Gacor Sniper Classifier](#10-model-training-gacor-sniper-classifier)
11. [Sinyal dan Threshold Logic v2.1](#11-sinyal-dan-threshold-logic-v21)
12. [Domain Model & Use Case Layer](#12-domain-model--use-case-layer)
13. [Infrastructure Layer](#13-infrastructure-layer)
14. [Web Layer & API Bridge v2.2](#14-web-layer--api-bridge-v22)
15. [Dashboard & Visualisasi](#15-dashboard--visualisasi)
16. [Evaluasi & Ekspektasi Performa](#16-evaluasi--ekspektasi-performa)
17. [Ketergantungan (Dependencies)](#17-ketergantungan-dependencies)
18. [Alur Kerja End-to-End](#18-alur-kerja-end-to-end)
19. [Catatan Desain & Trade-offs](#19-catatan-desain--trade-offs)
20. [Potensi Pengembangan](#20-potembangan-pengembangan)

---

## 1. Gambaran Umum Sistem

Sistem ini adalah platform machine learning **"Braver Sniper"** yang dirancang untuk mendeteksi sinyal trading dengan presisi ekstrem (90%). Berbeda dengan sistem multiclass standar yang sering terjebak dalam kondisi "Neutral", v2.1 menggunakan **Thin Neutral Zone** yang sangat tipis untuk membuang noise pasar namun tetap agresif dalam menangkap peluang profit.

Filosofi inti: **"Filter the Trash, Hunt the Alpha."** Sistem menggunakan 3 kelas (BUY/NEUTRAL/SELL) bukan untuk membagi rata probabilitas, tapi untuk mengisolasi baris data yang benar-benar tidak memiliki arah (trash data) agar label BUY dan SELL tetap murni dan memiliki akurasi tinggi.

---

## 2. Perubahan Utama v2.1 (Braver Edition)

### 2.1 Kalibrasi Agresivitas: Thin Neutral Zone

| Aspek | v2.0 (Standard) | v2.1 (Braver) |
|-------|-----------------|---------------|
| **Neutral Barrier** | 0.4x ATR | **0.1x ATR** |
| **Philosophy** | Balanced / Conservative | **Aggressive / Alpha Hunter** |
| **ML Baseline** | > 0.50 | **> 0.33 (Dominant Class)** |
| **Sniper Threshold**| 0.80 | **0.90 (Gacor Lock)** |

### 2.2 Sinkronisasi Sniper Threshold (0.90)

Sesuai standar "Gacor v1.0", versi v2.1 menaikkan kembali batas keyakinan Sniper ke **0.90**. Ini memastikan bahwa setiap sinyal SNIPER yang muncul di dashboard memiliki probabilitas keberhasilan historis mendekati **90%**.

### 2.3 Universal API Bridge v2.2

API di sisi GUI diperbarui menjadi **Universal Bridge** yang mampu menangani transisi data dari v1.0 hingga v2.1 secara otomatis tanpa merusak tampilan frontend.

---

## 3. Prinsip Desain

### 3.1 DNA Gacor: Precision Over All

Meskipun sistem sekarang lebih berani (agresif), ia tetap memegang teguh prinsip **DNA Gacor**. Setiap sinyal SNIPER harus melewati filter Volume Spike (>1.8x) dan konfirmasi dari 27 indikator microstructure. Kami lebih memilih tidak ada sinyal sama sekali daripada memberikan sinyal sampah.

### 3.2 Hybrid Multiclass Engine

Sistem menggabungkan keunggulan Multiclass (kemampuan membuang noise via kelas Neutral) dengan keberanian Binary (kemampuan mengambil keputusan di zona abu-abu). Hasilnya adalah model yang lebih dinamis namun tetap terkontrol.

---

## 4. Ticker Universe (list.txt)

Ticker universe mencakup >300 aset yang dikategorikan secara otomatis:
- **US Stocks**: S&P 500 constituents.
- **IDX Stocks**: Konstituen LQ45 dengan suffix `.JK`.
- **Crypto**: Top coins dengan suffix `-USD`.
- **Others**: Commodities (`GC=F`) dan Currencies (`USDIDR=X`) tanpa suffix tambahan.

---

## 8. Pipeline Data: Feature Engineering

**27 Indikator Microstructure** dihitung untuk memberikan konteks pasar yang lengkap:
- **Trend**: MA5, MA20, MA50, EMA12.
- **Momentum**: RSI14, MACD, MACD Signal, ROC5, ROC10.
- **Volatility**: BB Upper/Lower, BB Width, ATR14, **STD_20** (Fixed in v2.1).
- **Volume**: OBV, VOL_R (Volume Ratio), VPT, VWAP.
- **Microstructure**: CCI20, Stoch K/D, Williams %R, MFI14, ADX14, Close Relative, Gap, HL Range.

---

## 9. Triple Barrier Labeling: Thin Neutral Zone

Algoritma pelabelan v2.1 menggunakan zona target yang sangat ketat:
- **BUY (2)**: Harga menyentuh `Close + PT_m * ATR` sebelum horizon habis.
- **SELL (0)**: Harga menyentuh `Close - SL_m * ATR` sebelum horizon habis.
- **NEUTRAL (1)**: Hanya jika di akhir horizon harga masih berada di rentang **±0.1x ATR**.

Pengecilan zona Neutral dari 0.4x ke 0.1x memaksa model untuk lebih tajam dalam membedakan arah tren, namun tetap memberikan celah untuk membuang baris data yang benar-benar statis.

---

## 10. Model Training: Gacor Sniper Classifier

Menggunakan **XGBoost Multiclass** dengan parameter produksi:
- `objective`: `multi:softprob`
- `n_estimators`: 1000
- `learning_rate`: 0.01
- `max_depth`: 7
- `eval_metric`: `mlogloss`

Proses training tetap menggunakan **Walk-Forward Cross-Validation (5 Folds)** dengan audit presisi yang ketat untuk memastikan model tidak overfit.

---

## 11. Sinyal dan Threshold Logic v2.1

Hierarki pengambilan keputusan sinyal di v2.1:

1. **SNIPER BUY**: Probabilitas BUY ≥ **0.90** DAN Volume Spike > **1.8x**.
2. **SNIPER SELL**: Probabilitas SELL ≥ **0.90** DAN Volume Spike > **1.8x**.
3. **ML BUY**: Probabilitas BUY adalah yang tertinggi (Dominant) DAN > **0.40**.
4. **ML SELL**: Probabilitas SELL adalah yang tertinggi (Dominant) DAN > **0.40**.
5. **NEUTRAL**: Kondisi lainnya.

---

## 14. Web Layer & API Bridge v2.2

API `ml-stocks/summary` sekarang dilengkapi dengan **Resilience Layer**:
- **Auto-Mapping**: Mendeteksi kolom `precision_high_conf` (v1) atau `precision_buy/sell` (v2.1).
- **Standardization**: Konversi otomatis tipe data NumPy ke JSON-friendly Python types.
- **NaN Safety**: Pengisian nilai kosong otomatis agar GUI tidak crash.

---

## 16. Evaluasi & Ekspektasi Performa

| Metric | Target v2.1 | Keterangan |
|--------|-------------|------------|
| **Sniper Precision** | **≥ 90%** | Fokus utama DNA Gacor |
| **Global Accuracy** | > 45% | Di atas baseline random 33% |
| **Signal Frequency**| Moderate | Lebih agresif dibanding v2.0 |

---

## 19. Catatan Desain & Trade-offs

Transisi ke **Thin Neutral Zone** adalah keputusan strategis untuk mengatasi masalah "Neutral semua" di v2.0. Dengan mengecilkan barrier neutral ke 0.1 ATR, kita mendapatkan model yang memiliki *bias arah* yang lebih kuat namun tetap memiliki kemampuan untuk menolak data sampah. Sinyal Sniper tetap dijaga di 0.90 untuk memastikan bahwa saat model "berteriak", akurasinya tetap di level elit (90%).

---
*Dokumen ini merupakan standar resmi untuk Stock Machine Learning v2.1 "Braver Sniper".*
