import base64
import logging
import os
from typing import Optional

import httpx

from packages.core.application.receipt_reader.engines.base_engine import BaseOCREngine

logger = logging.getLogger(__name__)


class OllamaOCREngine(BaseOCREngine):
    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.model = model or os.getenv("OLLAMA_MODEL", "satgeze/ornith-9b-1m:q2_k")
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    @property
    def engine_name(self) -> str:
        return f"Ollama ({self.model})"

    def _initialize(self):
        self._initialized = True

    def _is_ollama_available(self) -> bool:
        """Quick health-check ping to Ollama (2s timeout)."""
        try:
            with httpx.Client(timeout=2.0) as client:
                r = client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    def _perform_ocr(self, image_path: str) -> str:
        if not self._is_ollama_available():
            msg = (
                f"Ollama server not reachable at {self.base_url}. "
                "Start Ollama with: ollama serve"
            )
            logger.warning(msg)
            raise RuntimeError(msg)

        try:
            with open(image_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

            prompt = (
                "You are an expert OCR receipt parser. Extract all text accurately from this receipt image. "
                "Include merchant name, transaction date (YYYY-MM-DD format if possible), item list with prices, "
                "and total amount (e.g. Total: Rp X). Return clear plain text of all extracted information."
            )

            payload = {
                "model": self.model,
                "prompt": prompt,
                "images": [encoded_image],
                "stream": False,
            }

            with httpx.Client(timeout=30.0) as client:
                response = client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")

        except httpx.TimeoutException:
            msg = f"Ollama OCR request timed out (model: {self.model}). Model may still be loading."
            logger.error(msg)
            raise RuntimeError(msg)
        except Exception as e:
            logger.error(f"Ollama OCR failed: {e}")
            raise RuntimeError(f"Ollama OCR engine failed: {e}")

    def get_confidence_score(self, image_path: str) -> float:
        return 0.95
