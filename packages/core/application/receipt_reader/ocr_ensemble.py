# core/ocr_ensemble.py
"""
OCR Ensemble: jalankan Tesseract + EasyOCR + PaddleOCR bersamaan,
pilih hasil terbaik berdasarkan confidence + voting field-level.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from packages.core.application.receipt_reader.engines.base_engine import BaseOCREngine


class MockOCREngine(BaseOCREngine):
    """Engine untuk testing, mengembalikan data dummy berdasarkan image path."""
    @property
    def engine_name(self) -> str:
        return "Mock"

    def _initialize(self):
        self._initialized = True

    def _perform_ocr(self, image_path: str) -> str:
        return """
        PEMBAYARAN QRIS BERHASIL
        pembayaran ke STARBUCKS
        Total: Rp 50.000
        Tanggal: 28/05/2026
        """

    def get_confidence_score(self, image_path: str) -> float:
        return 0.99


@dataclass
class EngineResult:
    engine_name: str
    raw_text: str
    confidence: float
    elapsed_ms: float
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.raw_text.strip())


@dataclass
class EnsembleResult:
    """Hasil gabungan semua engine."""
    best_text: str                          # Teks terpilih untuk parsing
    best_engine: str                        # Engine yang menang
    confidence: float                       # Confidence terpilih
    all_results: List[EngineResult] = field(default_factory=list)
    field_votes: Dict[str, str] = field(default_factory=dict)  # field → nilai terbaik
    engine_ranking: List[Tuple[str, float]] = field(default_factory=list)

    def summary(self) -> str:
        ok_results = [r for r in self.all_results if r.ok]
        failed = [r for r in self.all_results if not r.ok]
        available_count = len(ok_results)

        if available_count == 1:
            # Jujur: cuma 1 engine, tidak ada kompetisi
            lines = [f" {self.best_engine} ({self.confidence:.1%})"]
        else:
            lines = [f" {self.best_engine} menang ({self.confidence:.1%}) dari {available_count} engine"]
            for name, conf in self.engine_ranking:
                mark = "" if any(r.engine_name == name and r.ok for r in self.all_results) else "* "
                lines.append(f"  {mark}{name}: {conf:.1%}")

        # Tampilkan engine yang tidak terinstall secara ringkas
        if failed:
            missing = [r.engine_name for r in failed]
            lines.append(f"  [not installed: {', '.join(missing)}]")

        return "\n".join(lines)


class OCREnsemble:
    """
    Jalankan 3 engine OCR secara sekuensial (karena CPU-only),
    pilih hasil terbaik lewat confidence + field-level voting.

    Field voting: untuk field kritis (total, tanggal, merchant),
    nilai yang paling banyak disepakati 2/3 engine dipakai.
    """

    # Pola kritis yang dipakai untuk field voting
    _FIELD_PATTERNS = {
        "total": [
            r"(?:total|bayar|grand total|jumlah|amount)[^\d]*(?:Rp\s*)?(\d[\d.,]+)",
            r"(?:IDR|Rp)\s*(\d[\d.,]+)",
        ],
        "date": [
            r"(\d{2}[/-]\d{2}[/-]\d{4})",
            r"(\d{4}[/-]\d{2}[/-]\d{2})",
            r"(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})",
        ],
        "merchant": [
            r"[Pp]embayaran ke\s+(.+?)(?:\n|$)",
            r"[Mm]erchant\s*(?:name)?\s*[:\-]?\s*(.+?)(?:\n|$)",
            r"[Bb]eneficiary\s*[Nn]ame\s*(.+?)(?:\n|$)",
        ],
    }

    def __init__(self, language: str = "id", use_gpu: bool = False):
        self.language = language
        self.use_gpu = use_gpu
        self._engines: List[BaseOCREngine] = []
        self._available: List[str] = []
        self._load_engines()

    # ── Engine Loading ────────────────────────────────────────────────

    def _load_engines(self):
        """Load semua engine yang terinstall, skip yang tidak ada."""
        # Test/Mock mode support
        if os.environ.get("OCR_MOCK") == "true":
            self._engines.append(MockOCREngine(language=self.language))
            self._available.append("Mock")
            return

        candidates = [
            ("Gemini",    self._try_gemini),
            ("Ollama",    self._try_ollama),
            ("Tesseract", self._try_tesseract),
            ("EasyOCR",   self._try_easyocr),
            ("PaddleOCR", self._try_paddle),
        ]
        for name, loader in candidates:
            eng = loader()
            if eng:
                self._engines.append(eng)
                self._available.append(name)

        if not self._engines:
            raise RuntimeError(
                "Tidak ada OCR engine yang terinstall.\n"
                "Install minimal satu: gemini / ollama / pytesseract / easyocr / paddleocr"
            )

    def _try_ollama(self):
        try:
            from packages.core.application.receipt_reader.engines.ollama_engine import OllamaOCREngine
            return OllamaOCREngine(language=self.language)
        except Exception:
            return None

    def _try_gemini(self):
        try:
            import os
            if not os.environ.get("GEMINI_API_KEY"):
                return None
            from packages.core.application.receipt_reader.engines.gemini_engine import GeminiOCREngine
            return GeminiOCREngine(language=self.language)
        except Exception:
            # print(f"  [Gemini] GAGAL: {e}")
            return None

    def _try_tesseract(self):
        try:
            import os
            import sys

            import pytesseract

            from packages.core.application.receipt_reader.engines.tesseract_engine import TesseractEngine
            # Set Windows path DULU sebelum get_tesseract_version()
            if sys.platform == "win32":
                for path in [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                ]:
                    if os.path.isfile(path):
                        pytesseract.pytesseract.tesseract_cmd = path
                        break
            pytesseract.get_tesseract_version()
            return TesseractEngine(language=self.language)
        except Exception as e:
            print(f"  [Tesseract] GAGAL: {type(e).__name__}: {e}")
            return None

    def _try_easyocr(self):
        try:
            import easyocr  # noqa: F401

            from packages.core.application.receipt_reader.engines.easyocr_engine import EasyOCREngine
            return EasyOCREngine(language=self.language)
        except Exception:
            return None

    def _try_paddle(self):
        try:
            from paddleocr import PaddleOCR  # noqa: F401

            from packages.core.application.receipt_reader.engines.paddle_engine import PaddleOCREngine
            return PaddleOCREngine(language=self.language, use_gpu=self.use_gpu)
        except Exception:
            return None

    # ── Public API ────────────────────────────────────────────────────

    @property
    def available_engines(self) -> List[str]:
        return list(self._available)

    def run(self, image_path: str, verbose: bool = True, engine_name: Optional[str] = None) -> EnsembleResult:
        """
        Jalankan semua engine, pilih hasil terbaik.
        Jika engine_name diberikan, hanya jalankan engine tersebut.
        verbose=True → print progress per engine.
        """
        results: List[EngineResult] = []

        engines_to_run = self._engines
        if engine_name and engine_name.lower() != "auto":
            engines_to_run = [e for e in self._engines if e.engine_name.lower() == engine_name.lower()]

        for engine in engines_to_run:
            if verbose:
                print(f"  [{engine.engine_name}] scanning...", end=" ", flush=True)

            t0 = time.time()
            try:
                # extract_text() melakukan scan dan menyimpan hasil di cache engine
                text = engine.extract_text(image_path)
                # get_confidence_score() HARUS baca dari cache yg sama, tidak scan ulang
                conf = engine.get_confidence_score(image_path)
                elapsed = (time.time() - t0) * 1000
                results.append(EngineResult(
                    engine_name=engine.engine_name,
                    raw_text=text,
                    confidence=conf,
                    elapsed_ms=elapsed,
                ))
                if verbose:
                    print(f"conf={conf:.1%} ({elapsed:.0f}ms)")

                # Gemini-first logic: if Gemini is good enough, stop early to save time/local CPU
                if engine.engine_name == "Gemini" and conf > 0.8:
                    if verbose:
                        print("  [Ensemble] Gemini result strong (>80%), skipping local fallback.")
                    break

            except Exception as e:
                elapsed = (time.time() - t0) * 1000
                results.append(EngineResult(
                    engine_name=engine.engine_name,
                    raw_text="",
                    confidence=0.0,
                    elapsed_ms=elapsed,
                    error=str(e),
                ))
                if verbose:
                    print(f"FAILED ({e.__class__.__name__}: {str(e)[:60]})")

        return self._select_best(results)

    # ── Selection Logic ───────────────────────────────────────────────

    def _select_best(self, results: List[EngineResult]) -> EnsembleResult:
        ok_results = [r for r in results if r.ok]

        if not ok_results:
            # Semua gagal — kembalikan apapun yang ada
            fallback = results[0] if results else EngineResult("none", "", 0.0, 0.0)
            return EnsembleResult(
                best_text=fallback.raw_text,
                best_engine=fallback.engine_name,
                confidence=0.0,
                all_results=results,
                engine_ranking=[(r.engine_name, r.confidence) for r in results],
            )

        # Field-level voting untuk total, tanggal, merchant
        field_votes = self._vote_fields(ok_results)

        # Score setiap engine: confidence + bonus kalau field votes match
        scored = []
        for r in ok_results:
            score = r.confidence
            # Bonus: +0.05 per field yang match hasil voting
            for field_name, voted_val in field_votes.items():
                if voted_val and voted_val in r.raw_text:
                    score += 0.05
            scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best = scored[0]

        ranking = [(r.engine_name, r.confidence) for r in results]
        ranking.sort(key=lambda x: x[1], reverse=True)

        return EnsembleResult(
            best_text=best.raw_text,
            best_engine=best.engine_name,
            confidence=best.confidence,
            all_results=results,
            field_votes=field_votes,
            engine_ranking=ranking,
        )

    def _vote_fields(self, results: List[EngineResult]) -> Dict[str, str]:
        """
        Untuk setiap field kritis, cari nilai yang paling sering muncul
        di antara hasil engine (mayoritas 2/3).
        """
        voted: Dict[str, str] = {}

        for field_name, patterns in self._FIELD_PATTERNS.items():
            candidates: Dict[str, int] = {}

            for r in results:
                for pat in patterns:
                    m = re.search(pat, r.raw_text, re.IGNORECASE | re.MULTILINE)
                    if m:
                        val = m.group(1).strip()
                        if val:
                            # Normalize angka supaya "18.000" == "18,000"
                            norm = re.sub(r"[.,\s]", "", val) if field_name == "total" else val
                            candidates[norm] = candidates.get(norm, 0) + 1
                        break  # satu match per engine per field cukup

            if candidates:
                # Pilih yang paling banyak vote
                best_val = max(candidates, key=candidates.get)
                voted[field_name] = best_val

        return voted
