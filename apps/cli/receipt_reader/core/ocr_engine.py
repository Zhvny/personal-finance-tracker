from typing import Optional

from apps.cli.receipt_reader.core.engines.easyocr_engine import EasyOCREngine
from apps.cli.receipt_reader.core.engines.gemini_engine import GeminiOCREngine
from apps.cli.receipt_reader.core.engines.paddle_engine import PaddleOCREngine
from apps.cli.receipt_reader.core.interfaces import IOCREngine


class OCREngineFactory:
    @staticmethod
    def create_engine(preferred: Optional[str] = None, language: str = 'id', use_gpu: bool = False) -> IOCREngine:

        if preferred == 'gemini':
            return GeminiOCREngine(language=language)

        if preferred == 'paddle':
            try:
                return PaddleOCREngine(language=language, use_gpu=use_gpu)
            except ImportError:
                print("PaddleOCR not installed, trying fallback...")

        if preferred == 'easyocr':
            return EasyOCREngine(language=language)

        # Auto-detect priority: Gemini (if API Key) -> PaddleOCR -> EasyOCR
        import os
        if os.environ.get("GEMINI_API_KEY"):
            return GeminiOCREngine(language=language)

        try:
            return PaddleOCREngine(language=language, use_gpu=use_gpu)
        except ImportError:
            pass

        try:
            return EasyOCREngine(language=language)
        except RuntimeError:
            raise RuntimeError("No OCR engine available")
