# core/engines/paddle_engine.py
# PaddleOCR API berubah antar versi — 'show_log' dihapus di versi baru.
# Engine ini handle kedua versi secara graceful.
from .base_engine import BaseOCREngine


class PaddleOCREngine(BaseOCREngine):
    """OCR dengan PaddleOCR. Compatible dengan versi lama dan baru."""

    _paddle = None  # singleton

    @property
    def engine_name(self) -> str:
        return "PaddleOCR"

    def _initialize(self):
        if PaddleOCREngine._paddle is None:
            import logging

            from paddleocr import PaddleOCR
            logging.getLogger("ppocr").setLevel(logging.ERROR)

            use_gpu = getattr(self, "use_gpu", False)

            # Coba dengan show_log dulu (versi lama), fallback tanpa show_log (versi baru)
            for kwargs in [
                {"use_angle_cls": True, "lang": "en", "use_gpu": use_gpu, "show_log": False},
                {"use_angle_cls": True, "lang": "en", "use_gpu": use_gpu},
            ]:
                try:
                    PaddleOCREngine._paddle = PaddleOCR(**kwargs)
                    return
                except TypeError:
                    continue

            raise RuntimeError("PaddleOCR init gagal — semua kwargs dicoba")

    def _perform_ocr(self, image_path: str) -> str:
        result = PaddleOCREngine._paddle.ocr(image_path, cls=True)
        if not result or not result[0]:
            return ""
        lines = []
        for line in result[0]:
            if line and len(line) >= 2:
                text_info = line[1]
                if isinstance(text_info, (list, tuple)) and len(text_info) >= 1:
                    lines.append(str(text_info[0]))
        return '\n'.join(lines)

    def get_confidence_score(self, image_path: str) -> float:
        try:
            result = PaddleOCREngine._paddle.ocr(image_path, cls=True)
            if not result or not result[0]:
                return 0.0
            confs = []
            for line in result[0]:
                if line and len(line) >= 2:
                    text_info = line[1]
                    if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                        confs.append(float(text_info[1]))
            return sum(confs) / len(confs) if confs else 0.0
        except Exception:
            return 0.5
