"""
backend/ai/receipt_parser.py — Rule-Based Receipt Field Extraction
=================================================================
Standalone OCR-text → structured receipt dict.

Extracted from ai_rule_engine.py (Phase: R1 god-file split) so the insights
engine and the receipt parser can evolve independently. Receipt parsing has
no dependency on the 9 financial analyzers or the InsightComposer — it is
pure regex/keyword matching against a flat input string.

Public API:
  - RuleBasedReceiptParser.parse(text)  -> Dict[str, Any]
  - rule_based_receipt_parse(ocr_text)  -> Dict[str, Any]  (singleton wrapper)

Schema returned (stable contract — see tests/unit/test_receipt_parser.py):
  merchant_name:    str
  transaction_date: str  (ISO YYYY-MM-DD; falls back to today)
  total_amount:     float
  currency:         str  (always "IDR")
  payment_method:   str  (cash | debit_card | credit_card | e_wallet | transfer | qris)
  transaction_type: str  (always "expense")
  category:         str  (food | transport | shopping | health | entertainment | education | other)
  confidence:       float in [0.30, 0.85]
  items:            list
  notes:            str
  ai_analysis:      str
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict


class RuleBasedReceiptParser:
    """
    Extracts structured data from raw OCR text using pattern matching.
    Handles IDR amounts, common Indonesian merchant patterns, and date formats.
    """

    AMOUNT_PATTERNS = [
        r"total[:\s]+rp\.?\s*([\d.,]+)",
        r"jumlah[:\s]+rp\.?\s*([\d.,]+)",
        r"grand\s*total[:\s]+rp\.?\s*([\d.,]+)",
        r"rp\.?\s*([\d.,]+)",
        r"([\d]{1,3}(?:[.,]\d{3})+)",
    ]

    DATE_PATTERNS = [
        r"(\d{2})[/-](\d{2})[/-](\d{4})",   # DD/MM/YYYY
        r"(\d{4})[/-](\d{2})[/-](\d{2})",   # YYYY-MM-DD
        r"(\d{2})\s+(jan|feb|mar|apr|mei|jun|jul|agu|sep|okt|nov|des)\s+(\d{4})",
    ]

    MERCHANT_KEYWORDS = {
        "alfamart": "Alfamart", "indomaret": "Indomaret",
        "kfc": "KFC", "mcdonald": "McDonald's", "mcdonalds": "McDonald's",
        "grab": "GrabFood", "gojek": "GoFood", "shopee": "Shopee",
        "tokopedia": "Tokopedia", "starbucks": "Starbucks",
        "hypermart": "Hypermart", "transmart": "Transmart",
        "lawson": "Lawson", "circle k": "Circle K",
    }

    CATEGORY_KEYWORDS = {
        "food":          ["makanan", "makan", "food", "restoran", "warung", "cafe", "kopi",
                          "nasi", "mie", "ayam", "pizza", "burger", "sushi", "bakery"],
        "transport":     ["grab", "gojek", "ojek", "taksi", "taxi", "bus", "kereta",
                          "bensin", "parkir", "toll", "tol"],
        "shopping":      ["shopee", "tokopedia", "lazada", "baju", "sepatu", "fashion",
                          "clothing", "shirt", "pants", "dress"],
        "health":        ["apotek", "apotik", "pharmacy", "rumah sakit", "dokter",
                          "obat", "vitamin", "health", "klinik"],
        "entertainment": ["bioskop", "cinema", "game", "netflix", "spotify", "hiburan",
                          "konser", "tiket"],
        "education":     ["buku", "kursus", "les", "sekolah", "kampus", "ujian",
                          "education", "training"],
    }

    PAYMENT_KEYWORDS = {
        "qris":         ["qris", "qr code", "qr payment"],
        "debit_card":   ["debit", "kartu debit"],
        "credit_card":  ["kredit", "credit", "visa", "mastercard"],
        "e_wallet":     ["gopay", "ovo", "dana", "shopeepay", "linkaja", "e-wallet", "ewallet"],
        "transfer":     ["transfer", "bca", "bri", "bni", "mandiri", "seabank"],
        "cash":         ["cash", "tunai", "uang"],
    }

    def parse(self, text: str) -> Dict[str, Any]:
        import re
        text_lower = text.lower()

        # Amount
        amount = 0.0
        for pattern in self.AMOUNT_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                raw = match.group(1).replace(".", "").replace(",", "")
                try:
                    amount = float(raw)
                    if amount > 1_000_000_000:
                        amount /= 1000  # Likely formatting issue
                    break
                except ValueError:
                    pass

        # Date
        transaction_date = datetime.now().strftime("%Y-%m-%d")
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    g = match.groups()
                    if len(g) == 3 and len(g[0]) == 4:
                        transaction_date = f"{g[0]}-{g[1]}-{g[2]}"
                    elif len(g) == 3:
                        transaction_date = f"{g[2]}-{g[1]}-{g[0]}"
                    break
                except Exception:
                    pass

        # Merchant
        merchant_name = "Unknown Merchant"
        for kw, name in self.MERCHANT_KEYWORDS.items():
            if kw in text_lower:
                merchant_name = name
                break

        # Category
        category = "other"
        for cat, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                category = cat
                break

        # Payment method
        payment_method = "cash"
        for method, keywords in self.PAYMENT_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                payment_method = method
                break

        confidence = 0.55 if amount > 0 else 0.30
        if merchant_name != "Unknown Merchant":
            confidence += 0.10
        if transaction_date != datetime.now().strftime("%Y-%m-%d"):
            confidence += 0.10

        return {
            "merchant_name":    merchant_name,
            "transaction_date": transaction_date,
            "total_amount":     amount,
            "currency":         "IDR",
            "payment_method":   payment_method,
            "transaction_type": "expense",
            "category":         category,
            "confidence":       min(0.85, confidence),
            "items":            [],
            "notes":            "",
            "ai_analysis":      "Parsed via rule-based engine. Verifikasi data di bawah sebelum menyimpan.",
        }


_receipt_parser = RuleBasedReceiptParser()


def rule_based_receipt_parse(ocr_text: str) -> Dict[str, Any]:
    """
    Parse receipt text using rule-based pattern matching.
    Returns a dict compatible with the Claude/Ollama receipt schema.
    """
    return _receipt_parser.parse(ocr_text)
