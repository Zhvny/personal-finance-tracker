"""
Reward Catalogue CLI — Interactive Menu
Run: python cli.py
"""

import asyncio
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

# Attempt to import httpx for thumbnail pre-generation
try:
    import httpx
except ImportError:
    httpx = None

# ══════════════════════════════════════════════════════════════════════════════
# § DOMAIN
# ══════════════════════════════════════════════════════════════════════════════

VALID_TIERS = ["basic", "mid", "premium", "ultra"]
VALID_TYPES = ["Pack", "Photo", "Video", "Mixed"]
PHOTO_EXTS  = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTS  = {".mp4", ".mov", ".webm", ".mkv",".m4v"}

TIER_COST_DEFAULT = {"basic": 300, "mid": 600, "premium": 1000, "ultra": 2000}

@dataclass
class Reward:
    id: str; title: str; cost: int; season: int; tier: str; type: str

    def validate(self):
        e = []
        if not self.id.strip():          e.append("id kosong")
        if not self.title.strip():       e.append("title kosong")
        if self.cost <= 0:               e.append("cost harus > 0")
        if self.season < 0:              e.append("season harus >= 0")
        if self.tier not in VALID_TIERS: e.append(f"tier harus: {', '.join(VALID_TIERS)}")
        if self.type not in VALID_TYPES: e.append(f"type harus: {', '.join(VALID_TYPES)}")
        return e

    def to_manifest(self, contents=None):
        return {"id": self.id, "title": self.title, "cost": self.cost,
                "season": self.season, "tier": self.tier, "type": self.type,
                "contents": contents or []}

# ══════════════════════════════════════════════════════════════════════════════
# § INFRASTRUCTURE
# ══════════════════════════════════════════════════════════════════════════════

class Repo:
    def __init__(self):
        self.base        = Path(__file__).parent
        self.index_file  = self.base / "rewards-index.json"
        self.cache_dir   = self.base.parent.parent / "data" / "cache" / "thumbnails"

    def load_index(self):
        if not self.index_file.exists(): return []
        raw = self.index_file.read_text().strip()
        return json.loads(raw) if raw else []

    def save_index(self, ids):
        self.index_file.write_text(json.dumps(ids, indent=2))

    def reward_dir(self, rid):   return self.base / rid
    def manifest(self, rid):     return self.base / rid / "manifest.json"

    def load_manifest(self, rid):
        p = self.manifest(rid)
        return json.loads(p.read_text()) if p.exists() else None

    def save_manifest(self, r: Reward, contents=None):
        d = self.reward_dir(r.id); d.mkdir(parents=True, exist_ok=True)
        self.manifest(r.id).write_text(
            json.dumps(r.to_manifest(contents), indent=2, ensure_ascii=False))

    def delete(self, rid):
        p = self.manifest(rid)
        if p.exists(): p.unlink(); return True
        return False

    def next_id(self):
        nums = []
        for rid in self.load_index():
            p = rid.rsplit("-", 1)
            if len(p) == 2 and p[1].isdigit(): nums.append(int(p[1]))
        return f"reward-{max(nums, default=0) + 1}"

    def all(self):
        out = []
        for rid in self.load_index():
            m = self.load_manifest(rid)
            if m:
                out.append(Reward(id=m.get("id", rid), title=m.get("title",""),
                    cost=int(m.get("cost",0)), season=int(m.get("season",0)),
                    tier=m.get("tier","basic"), type=m.get("type","Pack")))
        return out

    def register(self, rid):
        idx = self.load_index()
        if rid not in idx: idx.append(rid); self.save_index(idx)

    def unregister(self, rid):
        self.save_index([i for i in self.load_index() if i != rid])

# ══════════════════════════════════════════════════════════════════════════════
# § UI HELPERS
# ══════════════════════════════════════════════════════════════════════════════

W = 58  # menu width

def clr():
    import subprocess

    subprocess.run(["cmd", "/c", "cls"] if os.name == "nt" else ["clear"], shell=False)

def hr(char="─"): print("  " + char * W)

def header(title=""):
    clr()
    print()
    hr("═")
    print(f"  {'REWARD CATALOGUE MANAGER':^{W}}")
    if title:
        print(f"  {title:^{W}}")
    hr("═")
    print()

def pause(msg="  Tekan Enter untuk lanjut..."):
    input(msg)

def ask(label, default="", required=True):
    hint = f" (default: {default})" if default else ""
    while True:
        val = input(f"  {label}{hint}: ").strip() or default
        if val or not required: return val
        print("  ! Tidak boleh kosong")

def ask_choice(label, choices, default=None):
    idx_default = (choices.index(default) + 1) if default in choices else None
    print(f"  {label}:")
    for i, c in enumerate(choices, 1):
        marker = " <" if c == default else ""
        print(f"    {i}. {c}{marker}")
    hint = f" (default: {idx_default})" if idx_default else ""
    while True:
        raw = input(f"  Pilih [1-{len(choices)}]{hint}: ").strip() or str(idx_default or "")
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1]
        print(f"  ! Masukkan angka 1–{len(choices)}")

def ask_int(label, default=None, min_val=None):
    hint = f" (default: {default})" if default is not None else ""
    while True:
        raw = input(f"  {label}{hint}: ").strip()
        if not raw and default is not None: return default
        if raw.lstrip("-").isdigit():
            v = int(raw)
            if min_val is not None and v < min_val:
                print(f"  ! Harus >= {min_val}"); continue
            return v
        print("  ! Masukkan angka")

def confirm(msg="  Lanjutkan?"):
    return input(f"{msg} [y/N] ").strip().lower() == "y"

def ok(msg):   print(f"\n  [OK] {msg}")
def err(msg):  print(f"\n  [!]  {msg}")
def info(msg): print(f"  {msg}")

# ══════════════════════════════════════════════════════════════════════════════
# § THUMBNAIL PRE-GENERATOR (ASYNC)
# ══════════════════════════════════════════════════════════════════════════════

async def download_thumb(client, drive_id, sz, cache_dir):
    """Download and cache a single thumbnail."""
    path = cache_dir / f"{drive_id}_{sz}.jpg"
    if path.exists(): return "HIT"

    urls = [
        f"https://drive.google.com/thumbnail?id={drive_id}&sz={sz}",
        f"https://lh3.googleusercontent.com/u/0/d/{drive_id}={sz}",
        f"https://drive.google.com/u/0/uc?id={drive_id}&export=download"
    ]
    for url in urls:
        try:
            res = await client.get(url, timeout=10.0)
            if res.status_code == 200 and len(res.content) > 500:
                path.write_bytes(res.content)
                return "NEW"
        except: continue
    return "FAIL"

async def run_pregen(repo: Repo):
    """Scan all manifests and pre-generate thumbnails for everything."""
    header("── Pre-Generate Thumbnails ──")
    if not httpx:
        err("Modul 'httpx' tidak ditemukan. Jalankan: pip install httpx")
        pause(); return

    info("Scanning catalogue...")
    rewards = repo.load_index()
    targets = []

    for rid in rewards:
        m = repo.load_manifest(rid)
        if not m: continue

        # 1. Main thumbnail
        tid = m.get("thumbnail")
        if tid and not tid.startswith("/") and not tid.startswith("http"):
            targets.append((tid, "w320"))

        # 2. Content thumbnails
        for item in m.get("contents", []):
            fid = item.get("drive_id")
            if fid:
                targets.append((fid, "w120"))
                if item.get("type") == "photo":
                    targets.append((fid, "w320"))

    if not targets:
        info("Tidak ada thumbnail Drive yang perlu di-generate.")
        pause(); return

    info(f"Ditemukan {len(targets)} target thumbnail.")
    if not confirm("Mulai download sekarang?"): return

    repo.cache_dir.mkdir(parents=True, exist_ok=True)

    stats = {"HIT": 0, "NEW": 0, "FAIL": 0}
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        tasks = [download_thumb(client, tid, sz, repo.cache_dir) for tid, sz in targets]

        # Process in chunks of 10 to not overwhelm connection
        chunk_size = 10
        for i in range(0, len(tasks), chunk_size):
            chunk = tasks[i:i+chunk_size]
            results = await asyncio.gather(*chunk)
            for r in results: stats[r] += 1
            print(f"  Progress: {min(i+chunk_size, len(tasks))}/{len(tasks)} done... ", end="\r")

    print("\n")
    ok("Pre-generation selesai!")
    info(f"  - Baru didownload : {stats['NEW']}")
    info(f"  - Sudah ada (HIT) : {stats['HIT']}")
    info(f"  - Gagal          : {stats['FAIL']}")
    print()
    pause()

# ══════════════════════════════════════════════════════════════════════════════
# § SCREENS
# ══════════════════════════════════════════════════════════════════════════════

def screen_main(repo: Repo):
    """Main menu loop."""
    while True:
        rewards = repo.all()
        header()
        print(f"  Rewards terdaftar : {len(rewards)}")
        print()
        hr()
        print("  1. Lihat semua reward")
        print("  2. Import folder konten")
        print("  3. Tambah reward manual")
        print("  4. Hapus reward")
        print("  5. Pre-generate thumbnails (Speed up GUI)")
        print("  0. Keluar")
        hr()
        print()
        choice = input("  Pilih: ").strip()
        print()

        if   choice == "1": screen_list(repo)
        elif choice == "2": screen_import(repo)
        elif choice == "3": screen_add(repo)
        elif choice == "4": screen_remove(repo)
        elif choice == "5": asyncio.run(run_pregen(repo))
        elif choice == "0": clr(); sys.exit(0)
        else:
            err("Pilihan tidak valid."); pause()


def screen_list(repo: Repo):
    """Show all rewards as a table."""
    header("── Daftar Reward ──")
    rewards = repo.all()
    if not rewards:
        info("(belum ada reward)")
        print()
        pause()
        return

    # Table
    print(f"  {'No':<4} {'ID':<12} {'Title':<26} {'Cost':>6}  {'Tier':<9} {'Type':<7} {'Season'}")
    hr()
    for i, r in enumerate(rewards, 1):
        title_trunc = r.title[:25] + "…" if len(r.title) > 25 else r.title
        print(f"  {i:<4} {r.id:<12} {title_trunc:<26} {r.cost:>6}  {r.tier:<9} {r.type:<7} {r.season}")
    hr()
    print(f"  Total: {len(rewards)} reward")
    print()

    # Allow drill-down into a reward detail
    raw = input("  Masukkan nomor untuk detail, atau Enter untuk kembali: ").strip()
    if raw.isdigit() and 1 <= int(raw) <= len(rewards):
        screen_detail(repo, rewards[int(raw) - 1])
    # else fall through back to main


def screen_detail(repo: Repo, r: Reward):
    """Show reward detail + contents list."""
    header(f"── Detail: {r.id} ──")
    print(f"  ID      : {r.id}")
    print(f"  Title   : {r.title}")
    print(f"  Cost    : {r.cost} Lust")
    print(f"  Tier    : {r.tier}")
    print(f"  Type    : {r.type}")
    print(f"  Season  : {r.season}")
    print()

    m = repo.load_manifest(r.id)
    contents = m.get("contents", []) if m else []
    if contents:
        print(f"  Konten ({len(contents)} file):")
        hr()
        for i, c in enumerate(contents, 1):
            print(f"  {i:>3}. [{c.get('type','?'):5}] {c.get('file','')}  —  {c.get('caption','')}")
        hr()
    else:
        info("  (tidak ada konten terdaftar di manifest)")
    print()
    pause()


def screen_import(repo: Repo):
    """Import a content folder — interactive."""
    header("── Import Folder Konten ──")
    print("  Folder akan diimport ke rewards/<reward-N>/")
    print("  Nama folder otomatis jadi judul di GUI.")
    print("  File di dalam folder akan di-rename ke:")
    print("    photo_1.jpg, photo_2.jpg, ... video_1.mp4, ...")
    print()
    hr()
    print()

    # ── Step 1: Folder path ───────────────────────────────────────────────────
    while True:
        raw = ask("Path folder konten")
        src = Path(raw).expanduser().resolve()
        if not src.exists():   err(f"Folder tidak ditemukan: {src}"); continue
        if not src.is_dir():   err(f"Bukan folder: {src}");           continue
        break

    # ── Step 2: Scan files ────────────────────────────────────────────────────
    photos, videos = [], []
    for f in sorted(src.iterdir()):
        if not f.is_file(): continue
        ext = f.suffix.lower()
        if ext in PHOTO_EXTS: photos.append(f)
        elif ext in VIDEO_EXTS: videos.append(f)

    total = len(photos) + len(videos)
    if total == 0:
        err("Tidak ada file media yang didukung di folder ini.")
        err(f"Photo: {', '.join(sorted(PHOTO_EXTS))}")
        err(f"Video: {', '.join(sorted(VIDEO_EXTS))}")
        print(); pause(); return

    # ── Step 3: Auto-detect & confirm metadata ────────────────────────────────
    auto_title  = re.sub(r"[_]+", " ", src.name).strip()
    auto_type   = ("Mixed" if photos and videos else "Video" if videos else "Photo")
    reward_id   = repo.next_id()
    dest_dir    = repo.reward_dir(reward_id)

    print()
    print(f"  Folder    : {src}")
    print(f"  Files     : {len(photos)} foto, {len(videos)} video  ({total} total)")
    print()
    hr()
    print("  Isi detail reward:")
    hr()
    print()

    title  = ask("Judul reward",   default=auto_title)
    tier   = ask_choice("Tier",    VALID_TIERS, default="basic")
    cost   = ask_int("Harga (Lust)", default=TIER_COST_DEFAULT.get(tier, 500), min_val=1)
    season = ask_int("Season (0 = Season 1)", default=0, min_val=0)
    rtype  = ask_choice("Tipe konten", VALID_TYPES, default=auto_type)

    # ── Step 4: Build rename plan ─────────────────────────────────────────────
    rename_plan = []
    for i, p in enumerate(photos, 1):
        rename_plan.append((p, f"photo_{i}{p.suffix.lower()}"))
    for i, v in enumerate(videos, 1):
        rename_plan.append((v, f"video_{i}{v.suffix.lower()}"))

    contents = []
    for _, new_name in rename_plan:
        ftype   = "photo" if new_name.startswith("photo_") else "video"
        stem    = re.sub(r"_(\d+)$", "", new_name.rsplit(".", 1)[0])
        caption = stem.replace("_", " ").title()
        contents.append({"file": new_name, "type": ftype, "caption": caption})

    # ── Step 5: Preview ───────────────────────────────────────────────────────
    print()
    hr()
    print("  Preview rename plan:")
    hr()
    print(f"  {'File asli':<40}  ->  File baru")
    hr("·")
    for src_f, new_name in rename_plan:
        print(f"  {src_f.name:<40}  ->  {new_name}")
    hr()
    print(f"  Dest  : {dest_dir}")
    print(f"  ID    : {reward_id}")
    print(f"  Title : {title}")
    print(f"  Tier  : {tier}  |  Cost: {cost} Lust  |  Season: {season}  |  Type: {rtype}")
    print()

    if not confirm("  Proses import?"):
        info("Import dibatalkan."); print(); pause(); return

    # ── Step 6: Execute ───────────────────────────────────────────────────────
    print()
    dest_dir.mkdir(parents=True, exist_ok=True)
    for src_f, new_name in rename_plan:
        shutil.copy2(src_f, dest_dir / new_name)
        print(f"  copied  {src_f.name}  ->  {new_name}")

    reward = Reward(id=reward_id, title=title, cost=cost,
                    season=season, tier=tier, type=rtype)
    repo.save_manifest(reward, contents)
    repo.register(reward_id)

    print()
    ok(f"'{title}' berhasil diimport sebagai {reward_id}")
    ok(f"manifest.json ditulis ({len(contents)} konten)")
    ok("rewards-index.json diupdate")
    print()
    pause()


def screen_add(repo: Repo):
    """Manually add a reward entry (no file import)."""
    header("── Tambah Reward Manual ──")
    reward_id = repo.next_id()
    print(f"  Auto ID: {reward_id}")
    print()

    title  = ask("Judul reward")
    tier   = ask_choice("Tier", VALID_TIERS, default="basic")
    cost   = ask_int("Harga (Lust)", default=TIER_COST_DEFAULT.get(tier, 500), min_val=1)
    season = ask_int("Season (0 = Season 1)", default=0, min_val=0)
    rtype  = ask_choice("Tipe konten", VALID_TYPES, default="Pack")

    print()
    hr()
    print(f"  ID     : {reward_id}")
    print(f"  Title  : {title}")
    print(f"  Tier   : {tier}  |  Cost: {cost} Lust  |  Season: {season}  |  Type: {rtype}")
    hr()
    print()

    if not confirm():
        info("Dibatalkan."); print(); pause(); return

    reward = Reward(id=reward_id, title=title, cost=cost,
                    season=season, tier=tier, type=rtype)
    errs = reward.validate()
    if errs:
        for e in errs: err(e)
        pause(); return

    repo.save_manifest(reward)
    repo.register(reward_id)

    ok(f"'{title}' ditambahkan sebagai {reward_id}")
    print()
    pause()


def screen_remove(repo: Repo):
    """Remove a reward — pick from list."""
    header("── Hapus Reward ──")
    rewards = repo.all()

    if not rewards:
        info("(belum ada reward)")
        print(); pause(); return

    print(f"  {'No':<4} {'ID':<12} {'Title'}")
    hr()
    for i, r in enumerate(rewards, 1):
        print(f"  {i:<4} {r.id:<12} {r.title}")
    hr()
    print()

    raw = input("  Nomor reward yang dihapus (atau Enter untuk batal): ").strip()
    if not raw: info("Dibatalkan."); print(); pause(); return

    if not raw.isdigit() or not (1 <= int(raw) <= len(rewards)):
        err("Nomor tidak valid."); pause(); return

    target = rewards[int(raw) - 1]
    print()
    print(f"  Akan dihapus: {target.id}  —  {target.title}")
    print("  (folder konten tidak dihapus, hanya entry dari index)")
    print()

    if not confirm("  Yakin hapus?"):
        info("Dibatalkan."); print(); pause(); return

    repo.delete(target.id)
    repo.unregister(target.id)
    ok(f"'{target.id}' dihapus dari catalogue")
    print()
    pause()


# ══════════════════════════════════════════════════════════════════════════════
# § ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    repo = Repo()
    try:
        screen_main(repo)
    except KeyboardInterrupt:
        clr()
        print("\n  Keluar.\n")
        sys.exit(0)
