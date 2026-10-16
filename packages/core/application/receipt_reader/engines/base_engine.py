from abc import ABC, abstractmethod

from packages.core.application.receipt_reader.interfaces import IOCREngine


class BaseOCREngine(IOCREngine, ABC):

    def __init__(self, language='id', **kwargs):
        self.language = language
        self.config = kwargs
        self._initialized = False

    @property
    @abstractmethod
    def engine_name(self) -> str:
        pass

    @abstractmethod
    def _initialize(self):
        pass

    @abstractmethod
    def _perform_ocr(self, image_path: str) -> str:
        pass

    def extract_text(self, image_path: str) -> str:
        if not self._initialized:
            self._initialize()
            self._initialized = True
        text = self._perform_ocr(image_path)
        return self._sanitize_text(text)

    def _sanitize_text(self, text: str) -> str:
        if not text:
            return text
        # Fix encoding artifacts (e.g., Â· -> ·, â†‘ -> ↑)
        # These occur when UTF-8 icons/symbols are mis-decoded as CP1252/ISO-8859-1
        replacements = {
            'Â·': '·', 'â†‘': '↑', 'â†“': '↓', 'â†’': '→', 'â†': '←',
            'âœ“': '✓', 'âœ–': '✖', 'â—ڈ': '●', 'â—‹': '○', 'â€¦': '...',
            'â€“': '-', 'â€”': '--', 'â€˜': "'", 'â€™': "'", 'â€œ': '"', 'â€': '"',
        }
        for artifact, correct in replacements.items():
            text = text.replace(artifact, correct)
        return text

    def get_confidence_score(self, image_path: str) -> float:
        """Default - override kalau perlu"""
        return 0.8
