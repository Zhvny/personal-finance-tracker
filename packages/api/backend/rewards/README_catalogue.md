# Reward Content System

## Cara Tambah/Edit Reward

Setiap reward punya folder sendiri: `reward-N/`

### Struktur folder:
```
public/rewards/
  reward-1/
    manifest.json     ← metadata + daftar file
    photo_1.jpg       ← foto (bisa jpg, png, webp)
    video_1.mp4       ← video (bisa mp4, mov, webm)
  reward-2/
    manifest.json
    ...
```

### manifest.json fields:
```json
{
  "id":       "reward-1",        ← harus sama dengan nama folder
  "title":    "Nama reward",
  "desc":     "Deskripsi singkat",
  "cost":     500,               ← harga dalam Reward
  "season":   0,                 ← 0 = season 1, 1 = season 2, dst
  "tier":     "basic",           ← basic | mid | premium | ultra
  "type":     "Pack",            ← label bebas (Pack, Collection, dll)
  "contents": [
    { "file": "photo_1.jpg", "type": "photo", "caption": "Judul foto" },
    { "file": "video_1.mp4", "type": "video", "caption": "Judul video" }
  ]
}
```

### Cara tambah reward baru:
1. Buat folder `reward-4/` (atau nama bebas)
2. Buat `manifest.json` di dalamnya
3. Taruh foto/video di folder itu
4. Selesai — app auto-detect dari `rewards-index.json`

### Update rewards-index.json:
Tambahkan path folder baru ke `rewards-index.json`:
```json
["reward-1", "reward-2", "reward-3", "reward-4"]
```
