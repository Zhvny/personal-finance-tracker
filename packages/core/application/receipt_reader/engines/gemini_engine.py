# apps/cli/receipt_reader/core/engines/gemini_engine.py
import json
import logging
import os
import threading
import time
from typing import Optional

from .base_engine import BaseOCREngine

logger = logging.getLogger(__name__)


class GeminiOCREngine(BaseOCREngine):
    """
    OCR Engine using Gemini 2.5 Flash via Google Generative AI SDK.
    Provides high accuracy and structured financial data extraction.
    """

    _api_keys = []
    _current_key_index = 0
    _penalty_box = {}  # key -> timestamp when it can be used again
    _key_lock = threading.Lock()

    def __init__(self, language="id", model_name="gemini-2.0-flash", **kwargs):
        super().__init__(language=language, **kwargs)
        self.model_name = model_name
        self._cache = {}
        self._confidence_cache = {}

    @property
    def engine_name(self) -> str:
        return "Gemini"

    def _get_next_key(self) -> Optional[str]:
        """Rotate through available API keys, skipping those in penalty box."""
        with GeminiOCREngine._key_lock:
            if not GeminiOCREngine._api_keys:
                raw_keys = os.environ.get("GEMINI_API_KEY", "")
                if not raw_keys:
                    return None
                GeminiOCREngine._api_keys = [k.strip() for k in raw_keys.replace(";", ",").split(",") if k.strip()]

            if not GeminiOCREngine._api_keys:
                return None

            now = time.time()
            num_keys = len(GeminiOCREngine._api_keys)

            for _ in range(num_keys):
                key = GeminiOCREngine._api_keys[GeminiOCREngine._current_key_index]
                GeminiOCREngine._current_key_index = (GeminiOCREngine._current_key_index + 1) % num_keys

                penalty_expiry = GeminiOCREngine._penalty_box.get(key, 0)
                if now >= penalty_expiry:
                    if key in GeminiOCREngine._penalty_box:
                        del GeminiOCREngine._penalty_box[key]
                    return key

            return min(GeminiOCREngine._api_keys, key=lambda k: GeminiOCREngine._penalty_box.get(k, 0))

    def _mark_key_failed(self, key: str, duration: int = 60):
        """Put a key in the penalty box."""
        print(f"[Gemini] Key rate limited. Cooldown: {duration}s")
        with GeminiOCREngine._key_lock:
            GeminiOCREngine._penalty_box[key] = time.time() + duration

    def _initialize(self):
        """Lazy initialization handled in _perform_ocr to allow better key rotation."""
        pass

    def _perform_ocr(self, image_path: str) -> str:
        """OCR with high-fidelity financial parsing and structured output."""
        if image_path in self._cache:
            return self._cache[image_path]

        try:
            import google.generativeai as genai
            from PIL import Image
        except ImportError:
            return "Error: google-generativeai or PIL not installed"

        max_retries = 2  # 1x initial + 1x retry
        last_error = None
        current_key = self._get_next_key()

        if not current_key:
            return "Error: No GEMINI_API_KEY found."

        genai.configure(api_key=current_key)
        model = genai.GenerativeModel(self.model_name)

        for attempt in range(max_retries):
            try:
                with Image.open(image_path) as img:
                    system_instruction = (
                        "You are an expert financial auditor. Extract data from the receipt image and return ONLY a JSON object. "
                        "Handle blurry thermal receipts with advanced vision context. "
                        "Follow this schema strictly:\n"
                        "{\n"
                        '  "merchant": "string",\n'
                        '  "date": "YYYY-MM-DD",\n'
                        '  "amount": number,\n'
                        '  "currency": "string",\n'
                        '  "type": "expense" | "income" | "transfer" | "investment",\n'
                        '  "category": "string",\n'
                        '  "payment_method": "string",\n'
                        '  "ticker": "string" (if stock/investment),\n'
                        '  "quantity": number (if stock/investment),\n'
                        '  "confidence": 0.0 to 1.0\n'
                        "}\n\n"
                        "Classification Logic:\n"
                        "- If text contains 'Transfer', 'TRF', 'Top Up', 'Withdraw', 'Transfer Received' -> type: 'transfer'.\n"
                        "- If it's a purchase of stock, crypto, or assets -> type: 'investment'.\n"
                        "- If it's a standard consumer purchase -> type: 'expense'.\n"
                        "- If it's a salary/deposit -> type: 'income'.\n"
                        "Maintain original merchant names. Date should be ISO format."
                    )

                    response = model.generate_content([system_instruction, img])
                    text = response.text.strip()

                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()

                self._cache[image_path] = text
                try:
                    js = json.loads(text)
                    self._confidence_cache[image_path] = float(js.get("confidence", 0.0))
                except (ValueError, TypeError, AttributeError) as exc:
                    logger.warning("Gemini confidence parse failed for %s: %s", image_path, exc)
                    self._confidence_cache[image_path] = 0.0

                return text
            except Exception as e:
                last_error = e
                err_msg = str(e).lower()

                is_rate_limit = "429" in err_msg or "resource_exhausted" in err_msg or "limit" in err_msg
                if is_rate_limit:
                    self._mark_key_failed(current_key, duration=60)

                if attempt < max_retries - 1:
                    current_key = self._get_next_key()
                    if current_key:
                        genai.configure(api_key=current_key)
                        model = genai.GenerativeModel(self.model_name)
                        continue
                break

        return f"Gemini Error: {str(last_error)}"

    def get_confidence_score(self, image_path: str) -> float:
        return self._confidence_cache.get(image_path, 0.0)
