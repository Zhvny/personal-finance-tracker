"""Task 9: Parity test for legacy frontend i18n dictionaries (TDD).

Ensures:
  1. Every key in en.js exists in id.js.
  2. Every key in id.js exists in en.js.
  3. No empty translations in either locale.
"""
import re
from pathlib import Path

_I18N_DIR = Path(__file__).resolve().parent.parent.parent / "packages" / "web" / "src" / "i18n"


def _extract_keys(file_path: Path):
    if not file_path.exists():
        raise FileNotFoundError(f"Missing dictionary file: {file_path}")
    text = file_path.read_text(encoding="utf-8")
    # Matches "key.name": or 'key.name':
    matches = re.findall(r'["\']([a-zA-Z0-9_.-]+)["\']\s*:\s*["\'](.*?)["\']', text)
    keys_dict = {k: v for k, v in matches}
    return keys_dict


def test_i18n_dictionary_files_exist():
    en_file = _I18N_DIR / "en.js"
    id_file = _I18N_DIR / "id.js"
    assert en_file.exists(), f"Missing {en_file}"
    assert id_file.exists(), f"Missing {id_file}"


def test_i18n_key_parity():
    en_dict = _extract_keys(_I18N_DIR / "en.js")
    id_dict = _extract_keys(_I18N_DIR / "id.js")

    en_keys = set(en_dict.keys())
    id_keys = set(id_dict.keys())

    missing_in_id = en_keys - id_keys
    missing_in_en = id_keys - en_keys

    assert not missing_in_id, f"Keys in en.js missing from id.js: {sorted(missing_in_id)}"
    assert not missing_in_en, f"Keys in id.js missing from en.js: {sorted(missing_in_en)}"
    assert len(en_keys) >= 40, f"Expected comprehensive dictionary (>= 40 keys), got {len(en_keys)}"


def test_no_empty_translations():
    en_dict = _extract_keys(_I18N_DIR / "en.js")
    id_dict = _extract_keys(_I18N_DIR / "id.js")

    for k, v in en_dict.items():
        assert v.strip(), f"Empty EN translation for key: {k}"
    for k, v in id_dict.items():
        assert v.strip(), f"Empty ID translation for key: {k}"
