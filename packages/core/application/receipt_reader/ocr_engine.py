from typing import Optional

from packages.core.application.receipt_reader.engines.easyocr_engine import EasyOCREngine
from packages.core.application.receipt_reader.engines.gemini_engine import GeminiOCREngine
from packages.core.application.receipt_reader.engines.ollama_engine import OllamaOCREngine
from packages.core.application.receipt_reader.engines.paddle_engine import PaddleOCREngine
from packages.core.application.receipt_reader.interfaces import IOCREngine


class OCREngineFactory:
    @staticmethod
    def create_engine(preferred: Optional[str] = None, language: str = 'id', use_gpu: bool = False) -> IOCREngine:

        if preferred == 'ollama':
            return OllamaOCREngine(language=language)

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
