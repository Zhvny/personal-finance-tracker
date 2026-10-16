
import pytesseract
from PIL import Image, ImageEnhance

from .base_engine import BaseOCREngine


def _is_screenshot(image_path: str) -> bool:
    """
    Heuristic: screenshot app cenderung PNG, lebar >=720px, dan aspect ratio portrait.
    Thermal receipt foto biasanya JPEG, lebar < 600px.
    """
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            fmt = (img.format or "").upper()
            aspect = h / w if w else 0
            # Screenshot: PNG, portrait, dan ukuran layar HP standar
            if fmt == "PNG" and aspect > 1.5 and w >= 720:
                return True
            # Sangat portrait (3:1+) dan besar = full screenshot
            if aspect >= 2.5 and w >= 360:
                return True
    except Exception:
        pass
    return False


class TesseractEngine(BaseOCREngine):
    """OCR menggunakan Tesseract — adaptif untuk struk fisik maupun screenshot app."""

    @property
    def engine_name(self) -> str:
        return "Tesseract"

    def _initialize(self):
        import os
        import sys
        # Windows: set path ke Tesseract kalau belum ada di PATH
        if sys.platform == "win32":
            candidates = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            for path in candidates:
                if os.path.isfile(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break
        try:
            pytesseract.get_tesseract_version()
        except Exception:
            raise RuntimeError("Tesseract not installed")
        # Pilih language pack: ind+eng > eng
        try:
            langs = pytesseract.get_languages(config="")
        except Exception:
            langs = ["eng"]
        if "ind" in langs:
            self._lang = "ind+eng"
        elif "eng" in langs:
            self._lang = "eng"
        else:
            self._lang = langs[0] if langs else "eng"

    def _preprocess_physical(self, img_raw: Image.Image) -> Image.Image:
        """Preprocessing untuk foto struk kertas termal."""
        img = img_raw.convert("RGB")
        w, h = img.size
        if w < 1000:
            scale = 1000 / w
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        img = img.convert("L")
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = ImageEnhance.Sharpness(img).enhance(1.5)
        return img

    def _preprocess_screenshot(self, img_raw: Image.Image) -> Image.Image:
        """
        Preprocessing untuk screenshot app (blu, BCA mobile, dll).
        Screenshot sudah tajam — jangan over-enhance, cukup scale dan grayscale.
        Contrast rendah agar teks putih di bg berwarna masih kebaca.
        """
        img = img_raw.convert("RGB")
        w, h = img.size
        # Screenshot HP biasanya 1080px, crop 20% sisi atas/bawah (status bar + navbar)
        top_crop = int(h * 0.08)
        bot_crop = int(h * 0.06)
        if bot_crop > 0:
            img = img.crop((0, top_crop, w, h - bot_crop))
        img = img.convert("L")
        # Ringan saja — layar HP sudah clear
        img = ImageEnhance.Contrast(img).enhance(1.3)
        return img

    def _preprocess(self, image_path: str) -> Image.Image:
        with Image.open(image_path) as img_raw:
            img_raw.load()
            if _is_screenshot(image_path):
                return self._preprocess_screenshot(img_raw.copy())
            return self._preprocess_physical(img_raw.copy())

    def _get_config(self, image_path: str) -> str:
        """
        Pilih PSM berdasarkan tipe gambar:
        - Screenshot (2-column layout app): PSM 6 (uniform block of text)
        - Struk fisik (single column):      PSM 4 (single column, variable size)
        """
        if _is_screenshot(image_path):
            # PSM 6: assume uniform block — bagus untuk layout 2-kolom rata
            return f"--oem 3 --psm 6 -l {self._lang}"
        # PSM 4: single column — bagus untuk struk kertas termal
        return f"--oem 3 --psm 4 -l {self._lang}"

    def _perform_ocr(self, image_path: str) -> str:
        img = self._preprocess(image_path)
        config = self._get_config(image_path)
        text = pytesseract.image_to_string(img, config=config)
        return text.strip()

    def get_confidence_score(self, image_path: str) -> float:
        try:
            img = self._preprocess(image_path)
            config = self._get_config(image_path)
            data = pytesseract.image_to_data(img, config=config,
                                              output_type=pytesseract.Output.DICT)
            confs = [int(c) for c in data["conf"]
                     if str(c).lstrip("-").isdigit() and int(c) > 0]
            return sum(confs) / len(confs) / 100 if confs else 0.0
        except Exception:
            return 0.0
