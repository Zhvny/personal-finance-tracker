import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from apps.cli.receipt_reader.core.interfaces import (
    ExpenseCategory,
    ICategoryClassifier,
    IncomeCategory,
    ReceiptData,
    TransactionType,
)


@dataclass
class ClassificationResult:
    category: Any
    confidence: float
    method: str
    matched_keywords: List[str]
    reasoning: str  # Explain why this category was chosen


class UniversalCategorizer(ICategoryClassifier):
    # LINGUISTIC PATTERNS - Language agnostic, not specific words
    PATTERNS = {
        ExpenseCategory.FOOD: {
            'consumption_verbs': ['eat', 'makan', 'dine', 'consume', 'minum', 'drink', 'order', 'pesan', 'beli'],
            'food_types': ['nasi', 'rice', 'mie', 'noodle', 'ayam', 'chicken', 'ikan', 'fish', 'daging', 'meat',
                          'sayur', 'vegetable', 'buah', 'fruit', 'snack', 'cemilan', 'dessert'],
            'meal_times': ['breakfast', 'lunch', 'dinner', 'sarapan', 'makan siang', 'makan malam'],
            'taste_words': ['delicious', 'lezat', 'enak', 'yummy', 'spicy', 'pedas', 'sweet', 'manis'],
            'context': ['restaurant', 'cafe', 'warung', 'kitchen', 'chef', 'menu', 'porsi', 'serving']
        },

        ExpenseCategory.TRANSPORT: {
            'movement_verbs': ['go', 'pergi', 'travel', 'commute', 'ride', 'naik', 'drive', 'mengemudi',
                              'send', 'kirim', 'deliver', 'antar'],
            'vehicles': ['car', 'mobil', 'motor', 'motorcycle', 'bus', 'train', 'kereta', 'plane', 'pesawat',
                        'taxi', 'ojek', 'gojek', 'grab'],
            'fuel': ['bensin', 'solar', 'fuel', 'gas', 'petrol', 'diesel', 'pertamina', 'shell'],
            'infrastructure': ['road', 'jalan', 'toll', 'highway', 'street', 'parking', 'parkir', 'station'],
            'trip_words': ['trip', 'perjalanan', 'journey', 'ride', 'fare', 'tarif', 'ongkir']
        },

        ExpenseCategory.SHOPPING: {
            'acquisition_verbs': ['buy', 'beli', 'purchase', 'shop', 'shopping', 'order', 'pesan'],
            'goods': ['baju', 'clothes', 'sepatu', 'shoes', 'tas', 'bag', 'elektronik', 'gadget',
                     'phone', 'laptop', 'furniture', 'mebel', 'accessories', 'aksesoris'],
            'commerce': ['store', 'toko', 'shop', 'mall', 'market', 'mart', 'online', 'e-commerce',
                        'discount', 'diskon', 'sale', 'promo', 'cashback'],
            'transaction': ['item', 'barang', 'product', 'produk', 'unit', 'pcs', 'quantity']
        },

        ExpenseCategory.ENTERTAINMENT: {
            'enjoyment_verbs': ['watch', 'nonton', 'play', 'main', 'enjoy', 'have fun', 'hang out'],
            'media': ['movie', 'film', 'cinema', 'bioskop', 'game', 'gaming', 'music', 'musik',
                     'concert', 'konser', 'show', 'performance'],
            'recreation': ['bowling', 'karaoke', 'timezone', 'arcade', 'fun', 'recreation', 'hobby'],
            'streaming': ['netflix', 'spotify', 'youtube', 'disney', 'streaming', 'subscription']
        },

        ExpenseCategory.HEALTH: {
            'medical_verbs': ['check', 'periksa', 'treat', 'obati', 'heal', 'sembuh', 'cure'],
            'facilities': ['hospital', 'rs', 'rumah sakit', 'clinic', 'klinik', 'pharmacy', 'apotek'],
            'professionals': ['doctor', 'dokter', 'nurse', 'perawat', 'dentist', 'gigi'],
            'medicine': ['obat', 'medicine', 'drug', 'pill', 'tablet', 'vitamin', 'supplement'],
            'wellness': ['fitness', 'gym', 'exercise', 'workout', 'healthy', 'sehat']
        },

        ExpenseCategory.HOUSING: {
            'dwelling': ['house', 'rumah', 'apartment', 'apt', 'kost', 'kos', 'rent', 'sewa', 'mortgage'],
            'utilities': ['electric', 'listrik', 'water', 'air', 'internet', 'wifi', 'gas'],
            'maintenance': ['repair', 'perbaikan', 'fix', 'service', 'clean', 'bersih', 'renovation'],
            'furniture': ['furniture', 'mebel', 'sofa', 'bed', 'kasur', 'table', 'meja', 'chair', 'kursi']
        },

        ExpenseCategory.EDUCATION: {
            'learning_verbs': ['learn', 'belajar', 'study', 'study', 'teach', 'ajar', 'train', 'latih'],
            'institutions': ['school', 'sekolah', 'university', 'univ', 'kampus', 'campus', 'course', 'kursus'],
            'materials': ['book', 'buku', 'textbook', 'modul', 'module', 'material', 'materi'],
            'fees': ['tuition', 'uang sekolah', 'fee', 'biaya', 'registration', 'pendaftaran']
        },

        ExpenseCategory.INVESTMENT: {
            'financial_verbs': ['invest', 'investasi', 'save', 'tabung', 'grow', 'kembang', 'return'],
            'instruments': ['stock', 'saham', 'bond', 'obligasi', 'crypto', 'bitcoin', 'mutual fund', 'reksadana',
                           'deposit', 'gold', 'emas', 'property', 'real estate'],
            'platforms': ['broker', 'sekuritas', 'exchange', 'trading', 'portfolio'],
            'returns': ['dividend', 'interest', 'bunga', 'capital gain', 'profit', 'return']
        }
    }

    # AMOUNT HEURISTICS - Typical ranges for each category (in IDR)
    AMOUNT_RANGES = {
        ExpenseCategory.FOOD: (5000, 500000),        # 5k - 500k
        ExpenseCategory.TRANSPORT: (3000, 200000),   # 3k - 200k
        ExpenseCategory.SHOPPING: (10000, 5000000),  # 10k - 5jt
        ExpenseCategory.ENTERTAINMENT: (20000, 500000),
        ExpenseCategory.HEALTH: (10000, 2000000),
        ExpenseCategory.HOUSING: (500000, 20000000), # 500k - 20jt
        ExpenseCategory.EDUCATION: (50000, 10000000),
        ExpenseCategory.INVESTMENT: (100000, 100000000),
    }

    # MERCHANT NAME PATTERNS - Structural analysis, not specific names
    MERCHANT_PATTERNS = {
        ExpenseCategory.FOOD: [
            r'\w+\s+(kitchen|cafe|resto|restaurant|warung|kedai|bakso|sate|nasi|mie|ayam)',  # "NARA KITCHEN"
            r'(kitchen|cafe|resto|warung|kedai)\s+\w+',  # "KEDAI KOPI"
        ],
        ExpenseCategory.TRANSPORT: [
            r'(gojek|grab|uber|taxi)\w*',
            r'\w+(pertamina|shell|bp|vivo)',
        ],
        ExpenseCategory.SHOPPING: [
            r'\w+(mart|store|shop|mall|plaza)',
            r'(toko|store|shop)\s+\w+',
        ],
    }

    def __init__(self):
        self.income_indicators = [
            'terima', 'received', 'income', 'pendapatan', 'gaji', 'salary',
            'transfer masuk', 'incoming', 'deposit', 'refund', 'pengembalian',
            'bonus', 'komisi', 'commission', 'dividen', 'dividend', 'bunga',
            'dana masuk', 'dari', 'from'
        ]
        self.transfer_indicators = [
            'transfer', 'trf', 'top up', 'topup', 'withdraw', 'tarik tunai',
            'va payment', 'virtual account', 'pindah buku', 'remit', 'transfer masuk'
        ]
        self.merchant_memory = {}

    def classify(self, receipt: ReceiptData) -> ClassificationResult:
        """Main classification method"""
        merchant = receipt.merchant_name.lower()
        text = receipt.raw_ocr_text.lower()

        # Step 0: Check for Transfers (Highest Priority)
        if any(k in merchant for k in self.transfer_indicators) or any(k in text for k in self.transfer_indicators):
            # Map to IncomeCategory.TRANSFER
            return ClassificationResult(
                category=IncomeCategory.TRANSFER,
                confidence=0.98,
                method='banking_logic',
                matched_keywords=[k for k in self.transfer_indicators if k in text or k in merchant],
                reasoning="Banking/Transfer terminology detected. Categorized as Transfer."
            )

        # Step 1: Check for specific user-requested mappings or hints
        food_merchants = ["m kubik", "mkubik", "nara kitchen", "ballin kitchen", "stay refreshed", "rasela"]
        if any(m in merchant for m in food_merchants):
            return ClassificationResult(
                category=ExpenseCategory.FOOD,
                confidence=1.0,
                method='user_defined_rule',
                matched_keywords=[merchant],
                reasoning=f"User mapping: {merchant} is categorized as Food"
            )

        income_people = ["ratnawati santoso", "joselyn", "ardiyanto"]
        if any(p in merchant for p in income_people):
            receipt.transaction_type = TransactionType.INCOME
            return ClassificationResult(
                category=IncomeCategory.OTHER,
                confidence=1.0,
                method='user_defined_rule',
                matched_keywords=[merchant],
                reasoning=f"User mapping: {merchant} is recognized as an Income source (Pocket Money)"
            )

        hint = receipt.metadata.get('description_hint', '').lower()
        if hint == 'pocket money':
            receipt.transaction_type = TransactionType.INCOME
            return ClassificationResult(
                category=IncomeCategory.OTHER,
                confidence=1.0,
                method='metadata_hint',
                matched_keywords=['pocket money'],
                reasoning="Using metadata hint: Pocket Money"
            )

        # Step 2: Detect transaction type (income vs expense)
        tx_type = self._detect_transaction_type(receipt)
        receipt.transaction_type = tx_type

        if tx_type == TransactionType.INCOME:
            return self._classify_income(receipt)

        # Step 3: Multi-factor analysis for expenses
        return self._classify_expense_universal(receipt)

    def classify_item(self, item_name: str) -> Optional[ExpenseCategory]:
        """Classify individual item"""
        item_lower = item_name.lower()
        scores = {}
        for category, patterns in self.PATTERNS.items():
            score = self._score_patterns(item_lower, patterns)
            scores[category] = score
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else None

    def _detect_transaction_type(self, receipt: ReceiptData) -> TransactionType:
        """Detect if income or expense"""
        text = receipt.raw_ocr_text.lower()
        merchant = receipt.merchant_name.lower()

        # Transfers are usually tracked as expense (outflow) in this system
        # unless explicitly "Transfer Received"
        if any(x in text for x in ['diterima', 'received', 'transfer masuk', 'incoming']):
            return TransactionType.INCOME

        income_score = sum(1 for ind in self.income_indicators if ind in text or ind in merchant)
        expense_indicators = ['bayar', 'payment', 'paid', 'purchase', 'beli', 'dibayar', 'checkout', 'order', 'pesan']
        expense_score = sum(1 for ind in expense_indicators if ind in text or ind in merchant)

        if 'pembayaran' in text and 'berhasil' in text:
            return TransactionType.EXPENSE

        return TransactionType.INCOME if income_score > expense_score else TransactionType.EXPENSE

    def _classify_expense_universal(self, receipt: ReceiptData) -> ClassificationResult:
        text = f"{receipt.merchant_name} {receipt.raw_ocr_text}".lower()
        merchant = receipt.merchant_name.lower()
        amount = receipt.total_amount.amount

        linguistic_scores = {}
        for category, patterns in self.PATTERNS.items():
            score = self._score_patterns(text, patterns)
            linguistic_scores[category] = score

        structure_score = self._analyze_merchant_structure(merchant)
        amount_score = self._score_amount(amount)
        context_score = self._analyze_context(receipt)

        final_scores = {}
        for cat in ExpenseCategory:
            if cat == ExpenseCategory.OTHER: continue
            final_scores[cat] = (
                linguistic_scores.get(cat, 0) * 0.5 +
                structure_score.get(cat, 0) * 0.25 +
                amount_score.get(cat, 0) * 0.15 +
                context_score.get(cat, 0) * 0.10
            )

        best_category = max(final_scores, key=final_scores.get)
        best_score = final_scores[best_category]

        if best_score < 1.0:
            best_category = ExpenseCategory.OTHER
            confidence = 0.3
            reasoning = "Low confidence - ambiguous signals"
        else:
            confidence = min(best_score / 10, 1.0)
            reasoning = self._generate_reasoning(best_category, text, amount)

        matched = self._get_matched_keywords(text, best_category)
        return ClassificationResult(category=best_category, confidence=confidence, method='universal_multi_factor', matched_keywords=matched, reasoning=reasoning)

    def _score_patterns(self, text: str, patterns: Dict[str, List[str]]) -> int:
        score = 0
        for category, keywords in patterns.items():
            matches = [k for k in keywords if k in text]
            score += len(matches) * 2
            for keyword in keywords:
                if re.search(r'\b' + re.escape(keyword) + r'\b', text):
                    score += 3
        return score

    def _analyze_merchant_structure(self, merchant: str) -> Dict[ExpenseCategory, float]:
        scores = {cat: 0.0 for cat in ExpenseCategory}
        for category, patterns in self.MERCHANT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, merchant, re.IGNORECASE):
                    scores[category] += 5.0
        return scores

    def _score_amount(self, amount: float) -> Dict[ExpenseCategory, float]:
        scores = {cat: 0.0 for cat in ExpenseCategory}
        for category, (min_amt, max_amt) in self.AMOUNT_RANGES.items():
            if min_amt <= amount <= max_amt:
                center = (min_amt + max_amt) / 2
                distance = abs(amount - center) / center
                scores[category] = max(0, 3 - distance * 3)
        return scores

    def _analyze_context(self, receipt: ReceiptData) -> Dict[ExpenseCategory, float]:
        scores = {cat: 0.0 for cat in ExpenseCategory}
        text = receipt.raw_ocr_text.lower()
        hour = receipt.transaction_date.hour if receipt.transaction_date else 12
        if 7 <= hour <= 9:
            scores[ExpenseCategory.TRANSPORT] += 2
            scores[ExpenseCategory.FOOD] += 1
        elif 12 <= hour <= 14:
            scores[ExpenseCategory.FOOD] += 3
        elif 18 <= hour <= 21:
            scores[ExpenseCategory.FOOD] += 2
            scores[ExpenseCategory.ENTERTAINMENT] += 2
        if 'qris' in text:
            scores[ExpenseCategory.FOOD] += 1
            scores[ExpenseCategory.TRANSPORT] += 1
        return scores

    def _get_matched_keywords(self, text: str, category: ExpenseCategory) -> List[str]:
        patterns = self.PATTERNS.get(category, {})
        all_keywords = []
        for cat_list in patterns.values():
            all_keywords.extend(cat_list)
        matched = [k for k in all_keywords if k in text]
        return list(set(matched))[:5]

    def _generate_reasoning(self, category: ExpenseCategory, text: str, amount: float) -> str:
        reasons = {
            ExpenseCategory.FOOD: f"Food-related terms found, amount Rp{amount:,.0f} typical for meal",
            ExpenseCategory.TRANSPORT: f"Movement/vehicle terms detected, amount Rp{amount:,.0f} fits transport",
            ExpenseCategory.SHOPPING: "Purchase/commerce indicators present",
            ExpenseCategory.ENTERTAINMENT: "Entertainment/recreation context",
            ExpenseCategory.HEALTH: "Medical/healthcare indicators",
            ExpenseCategory.HOUSING: "Housing/utilities context",
            ExpenseCategory.EDUCATION: "Learning/education indicators",
            ExpenseCategory.INVESTMENT: "Financial/investment terms found",
        }
        return reasons.get(category, "General expense")

    def _classify_income(self, receipt: ReceiptData) -> ClassificationResult:
        text = receipt.raw_ocr_text.lower()
        salary_indicators = ['gaji', 'salary', 'payroll', 'monthly']
        freelance_indicators = ['freelance', 'project', 'consultation', 'jasa']
        investment_indicators = ['dividend', 'bunga', 'interest', 'return']
        side_hustle_indicators = ['side', 'sampingan', 'part time', 'reseller']
        transfer_indicators = self.transfer_indicators

        scores = {
            IncomeCategory.SALARY: sum(1 for k in salary_indicators if k in text),
            IncomeCategory.FREELANCE: sum(1 for k in freelance_indicators if k in text),
            IncomeCategory.INVESTMENT: sum(1 for k in investment_indicators if k in text),
            IncomeCategory.SIDE_HUSTLE: sum(1 for k in side_hustle_indicators if k in text),
            IncomeCategory.TRANSFER: sum(1 for k in transfer_indicators if k in text),
            IncomeCategory.OTHER: 0,
        }
        best = max(scores, key=scores.get)
        if scores[best] == 0: best = IncomeCategory.OTHER
        return ClassificationResult(category=best, confidence=min(scores[best] / 3, 1.0), method='income_keywords', matched_keywords=[], reasoning=f"Income detected: {best.value}")
