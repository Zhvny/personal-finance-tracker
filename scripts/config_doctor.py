"""
config_doctor.py — cek kesehatan konfigurasi Alpha tanpa nyalain service.

Pakai (dari root Alpha):
    python scripts/config_doctor.py            # cek + laporan
Exit code: 0 = lolos, 1 = ada FAIL.
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "apps" / "api"))

results = []


def check(name: str, ok: bool, detail: str = ""):
    results.append((ok, name, detail))


def main():
    try:
        from apps.api.config import settings
    except Exception as e:
        print(f"[FAIL] Config gagal di-load: {e}")
        sys.exit(1)

    # 1. Secret key
    default_secret = "alpha-microservice-default-secret-key"
    check(
        "SECRET_KEY bukan nilai default",
        settings.SECRET_KEY != default_secret or settings.DEBUG or settings.TESTING,
        "default + DEBUG=off = bahaya produksi" if settings.SECRET_KEY == default_secret else "",
    )

    # 2. CORS tidak wildcard
    wildcard = any(o.strip() == "*" for o in settings.ALLOWED_ORIGINS)
    check("CORS tidak wildcard (*)", not wildcard, ", ".join(settings.ALLOWED_ORIGINS))

    # 3. Sertifikat SSL (kalau nggak ada → jalan HTTP; bukan fatal)
    certs_ok = settings.SSL_CERT_PATH.exists() and settings.SSL_KEY_PATH.exists()
    check(
        "Sertifikat SSL tersedia",
        certs_ok,
        f"{settings.SSL_CERT_PATH}" if certs_ok else f"tidak ketemu: {settings.SSL_CERT_PATH} (mode HTTP)",
    )

    # 4. DATABASE_URL
    db_url = getattr(settings, "DATABASE_URL", "")
    check("DATABASE_URL terisi", bool(db_url), db_url.split("@")[-1] if "@" in db_url else "(kosong)")

    # 5. Port registry (gateway 8444, services 8450-8455)
    gw = int(os.getenv("ALPHA_GATEWAY_PORT", "8444"))
    svc = list(range(8450, 8456))
    allp = [gw] + svc
    check("Port registry unik", len(set(allp)) == len(allp), f"gateway={gw}, services={svc[0]}-{svc[-1]}")

    # Laporan
    fails = 0
    for ok, name, detail in results:
        mark = "OK  " if ok else "FAIL"
        if not ok:
            fails += 1
        print(f"[{mark}] {name}" + (f"  ({detail})" if detail else ""))
    print(f"\n{len(results) - fails}/{len(results)} lolos.")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
