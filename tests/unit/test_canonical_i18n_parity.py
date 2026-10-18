"""Task 10: Parity test for canonical (apps/web) frontend i18n dictionaries (TDD).

Ensures:
  1. Every key in en.ts exists in id.ts.
  2. Every key in id.ts exists in en.ts.
  3. No empty translations in either locale.
"""
import re
from pathlib import Path
import pytest

_I18N_DIR = Path(__file__).resolve().parent.parent.parent / "apps" / "web" / "src" / "i18n"


def _extract_keys(file_path: Path):
    if not file_path.exists():
        raise FileNotFoundError(f"Missing dictionary file: {file_path}")
    text = file_path.read_text(encoding="utf-8")
    matches = re.findall(r'["\']([a-zA-Z0-9_.-]+)["\']\s*:\s*["\'](.*?)["\']', text)
    keys_dict = {k: v for k, v in matches}
    return keys_dict


def test_canonical_i18n_files_exist():
    en_file = _I18N_DIR / "en.ts"
    id_file = _I18N_DIR / "id.ts"
    assert en_file.exists(), f"Missing {en_file}"
    assert id_file.exists(), f"Missing {id_file}"


def test_canonical_key_parity():
    en_dict = _extract_keys(_I18N_DIR / "en.ts")
    id_dict = _extract_keys(_I18N_DIR / "id.ts")

    en_keys = set(en_dict.keys())
    id_keys = set(id_dict.keys())

    missing_in_id = en_keys - id_keys
    missing_in_en = id_keys - en_keys

    assert not missing_in_id, f"Keys in en.ts missing from id.ts: {sorted(missing_in_id)}"
    assert not missing_in_en, f"Keys in id.ts missing from en.ts: {sorted(missing_in_en)}"
    assert len(en_keys) >= 20, f"Expected dictionary (>= 20 keys), got {len(en_keys)}"


def test_canonical_no_empty_translations():
    en_dict = _extract_keys(_I18N_DIR / "en.ts")
    id_dict = _extract_keys(_I18N_DIR / "id.ts")

    for k, v in en_dict.items():
        assert v.strip(), f"Empty EN translation for key: {k}"
    for k, v in id_dict.items():
        assert v.strip(), f"Empty ID translation for key: {k}"
