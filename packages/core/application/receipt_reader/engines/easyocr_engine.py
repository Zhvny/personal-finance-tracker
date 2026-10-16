# core/engines/easyocr_engine.py
import re

import numpy as np
from PIL import Image, ImageEnhance

from .base_engine import BaseOCREngine


class EasyOCREngine(BaseOCREngine):
    """OCR dengan EasyOCR. Input ke readtext() selalu numpy array (paling kompatibel)."""

    _reader = None  # singleton — model berat, load sekali

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache: dict = {}  # path → raw result list

    @property
    def engine_name(self) -> str:
        return "EasyOCR"

    def _initialize(self):
        if EasyOCREngine._reader is None:
            import easyocr
            print("[EasyOCR] Loading model...")
            # Detect GPU availability
            gpu_available = False
            try:
                import torch
                gpu_available = torch.cuda.is_available()
            except ImportError:
                pass
            EasyOCREngine._reader = easyocr.Reader(["id", "en"], gpu=gpu_available)
            if gpu_available:
                import torch
                print(f"[EasyOCR] Using GPU: {torch.cuda.get_device_name(0)}")

    def _preprocess(self, image_path: str) -> np.ndarray:
        """Load + preprocess → numpy array RGB (format paling aman untuk EasyOCR)."""
        with Image.open(image_path) as img_raw:
            img = img_raw.convert("RGB")
            # Scale up supaya teks kecil lebih terbaca
            w, h = img.size
            if w < 1000:
                scale = 1000 / w
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            img = ImageEnhance.Contrast(img).enhance(1.8)
            img = ImageEnhance.Sharpness(img).enhance(1.5)
            return np.array(img)

    def _get_raw_result(self, image_path: str):
        """Scan gambar → cache [(bbox, text, conf), ...]."""
        if image_path not in self._cache:
            arr = self._preprocess(image_path)
            self._cache[image_path] = EasyOCREngine._reader.readtext(arr, detail=1)
        return self._cache[image_path]

    def _fix_ocr_noise(self, text: str) -> str:
        text = re.sub(r'[@©][Rr]\b', 'QR', text)           # @R → QR
        text = re.sub(r'(?<=\d)[oO](?=\d)', '0', text)     # O → 0 antar digit
        text = re.sub(r'(?<=\d)[lLIi](?=\d)', '1', text)   # l → 1 antar digit
        text = re.sub(r'\bOB\b', 'DB', text)                # OB → DB (Tesseract juga)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
        return text

    def _perform_ocr(self, image_path: str) -> str:
        result = self._get_raw_result(image_path)
        text = '\n'.join(item[1] for item in result)
        return self._fix_ocr_noise(text)

    def get_confidence_score(self, image_path: str) -> float:
        result = self._get_raw_result(image_path)
        if not result:
            return 0.0
        confs = [item[2] for item in result if len(item) >= 3]
        return sum(confs) / len(confs) if confs else 0.0
