from typing import Dict, Set

from packages.core.application.receipt_reader.interfaces import (
    ExpenseCategory,
    IncomeCategory,
)


class ExpenseKeywordDatabase:
    """Keywords untuk 8 categories di Finance Tracker"""

    # FOOD - 120+ keywords
    FOOD_KEYWORDS: Set[str] = frozenset({
        'restaurant', 'cafe', 'coffee shop', 'warung', 'rumah makan', 'kedai',
        'kfc', 'mcdonalds', 'mcd', 'burger king', 'pizza hut', 'dominos',
        'starbucks', 'excelso', 'jco', 'dunkin', 'breadtalk',
        'solaria', 'bakmi gm', 'bakso', 'sate', 'padang', 'sederhana',
        'ayam geprek', 'ayam penyet', 'bebek goreng', 'nasi goreng', 'mie ayam',
        'warteg', 'pecel lele', 'kaki lima', 'food court', 'food stall',
        'fast food', 'junk food', 'snack', 'cemilan', 'gorengan',
        'indomaret', 'alfamart', 'circle k', '7-eleven', 'supermarket',
        'minuman', 'kopi', 'teh', 'susu', 'yogurt', 'jus', 'smoothie',
        'soda', 'aqua', 'le minerale', 'nasi', 'mie', 'pasta', 'burger',
        'gofood', 'grabfood', 'shopeefood', 'delivery', 'gojek', 'grab',
    })

    # TRANSPORT - 110+ keywords
    TRANSPORT_KEYWORDS: Set[str] = frozenset({
        'gojek', 'grab', 'uber', 'maxim', 'ojek', 'ojol', 'motorcycle taxi',
        'taxi', 'taksi', 'blue bird', 'silver bird', 'express',
        'bus', 'transjakarta', 'mrt', 'lrt', 'krl', 'commuter line', 'kereta',
        'train', 'angkot', 'mikrolet', 'metromini', 'damri', 'busway',
        'pertamina', 'shell', 'bp', 'total', 'bensin', 'solar', 'bbm',
        'fuel', 'gasoline', 'diesel', 'pertalite', 'pertamax',
        'parkir', 'parking', 'toll', 'tol', 'gerbang tol', 'e-toll',
        'service', 'servis', 'bengkel', 'repair', 'sparepart', 'oli',
        'rental', 'sewa', 'leasing', 'flight', 'pesawat', 'airport',
    })

    # HOUSING - 90+ keywords
    HOUSING_KEYWORDS: Set[str] = frozenset({
        'sewa rumah', 'rent', 'rental', 'kontrakan', 'kost', 'kos', 'apartemen',
        'apartment', 'mortgage', 'kpr', 'kredit rumah', 'cicilan rumah',
        'maintenance', 'perbaikan rumah', 'renovasi', 'tukang', 'service ac',
        'pln', 'listrik', 'token listrik', 'pdam', 'air', 'internet', 'wifi',
        'security', 'satpam', 'cctv', 'cleaning service', 'pembantu',
        'ikea', 'informa', 'ace hardware', 'furniture', 'mebel', 'sofa',
    })

    # ENTERTAINMENT - 90+ keywords
    ENTERTAINMENT_KEYWORDS: Set[str] = frozenset({
        'bioskop', 'cinema', 'xxi', 'cgv', 'movie', 'film', 'tiket nonton',
        'concert', 'konser', 'festival', 'event', 'ticket',
        'game', 'gaming', 'playstation', 'steam', 'mobile legend', 'pubg',
        'timezone', 'bowling', 'karaoke', 'inul vizta', 'waterboom',
        'netflix', 'spotify', 'youtube premium', 'disney plus', 'hbo',
        'gym', 'fitness', 'fitness first', 'gold gym',
    })

    # HEALTH - 100+ keywords (bukan HEALTHCARE!)
    HEALTH_KEYWORDS: Set[str] = frozenset({
        'rumah sakit', 'hospital', 'rs', 'rsud', 'klinik', 'clinic',
        'mayapada', 'siloam', 'mitra keluarga', 'apotek', 'pharmacy',
        'apotik', 'kimia farma', 'guardian', 'watsons',
        'dokter', 'doctor', 'dental', 'gigi', 'bedah', 'surgery',
        'lab', 'laboratorium', 'medical checkup', 'mcu', 'rontgen',
        'obat', 'medicine', 'vitamin', 'suplemen', 'bpjs',
        'asuransi kesehatan', 'prudential', 'allianz', 'manulife',
    })

    # SHOPPING - 130+ keywords
    SHOPPING_KEYWORDS: Set[str] = frozenset({
        'tokopedia', 'shopee', 'shop33', 'sh0pee', 'shopee id', 'lazada', 'bukalapak', 'blibli', 'amazon',
        'fashion', 'pakaian', 'baju', 'kaos', 'kemeja', 'celana', 'jeans',
        'sepatu', 'shoes', 'tas', 'bag', 'nike', 'adidas', 'puma',
        'elektronik', 'gadget', 'hp', 'laptop', 'computer', 'samsung',
        'apple', 'xiaomi', 'oppo', 'vivo', 'erafone', 'ibox',
        'mall', 'plaza', 'department store', 'matahari', 'ramayana',
    })

    # EDUCATION - 80+ keywords
    EDUCATION_KEYWORDS: Set[str] = frozenset({
        'sekolah', 'school', 'universitas', 'university', 'kampus',
        'ui', 'itb', 'ugm', 'unair', 'binus', 'kursus', 'course',
        'training', 'workshop', 'seminar', 'bootcamp', 'coding',
        'ruangguru', 'zenius', 'coursera', 'udemy', 'skillshare',
        'buku', 'textbook', 'gramedia', 'modul', 'beasiswa',
    })

    # INVESTMENT - 100+ keywords
    INVESTMENT_KEYWORDS: Set[str] = frozenset({
        'saham', 'stock', 'bursa efek', 'bei', 'sekuritas', 'mirae asset',
        'reksadana', 'mutual fund', 'etf', 'manulife', 'schroder',
        'obligasi', 'bond', 'sukuk', 'crypto', 'bitcoin', 'ethereum',
        'binance', 'indodax', 'emas', 'gold', 'logam mulia', 'antam',
        'unit link', 'wealth management', 'deposito', 'tabungan berjangka',
    })

    # OTHER - fallback
    OTHER_KEYWORDS: Set[str] = frozenset({
        'lainnya', 'other', 'miscellaneous', 'biaya admin', 'admin fee',
        'pocket money', 'uang jajan', 'angpao', 'hadiah', 'gift',
    })

    # INCOME INDICATORS - untuk detect income vs expense
    INCOME_INDICATORS: Set[str] = frozenset({
        'terima', 'received', 'income', 'pendapatan', 'gaji', 'salary',
        'transfer masuk', 'deposit', 'refund', 'pengembalian', 'cashback',
        'bonus', 'komisi', 'commission', 'dividen', 'dividend', 'bunga',
        'freelance', 'project', 'invoice paid', 'sales', 'revenue',
        'dana masuk', 'dari', 'from',
    })

    @classmethod
    def get_all_keywords(cls) -> Dict[ExpenseCategory, Set[str]]:
        """Factory method - hanya 8 categories sesuai Finance Tracker"""
        return {
            ExpenseCategory.FOOD: cls.FOOD_KEYWORDS,
            ExpenseCategory.TRANSPORT: cls.TRANSPORT_KEYWORDS,
            ExpenseCategory.HOUSING: cls.HOUSING_KEYWORDS,
            ExpenseCategory.ENTERTAINMENT: cls.ENTERTAINMENT_KEYWORDS,
            ExpenseCategory.HEALTH: cls.HEALTH_KEYWORDS,  # health, bukan healthcare!
            ExpenseCategory.SHOPPING: cls.SHOPPING_KEYWORDS,
            ExpenseCategory.EDUCATION: cls.EDUCATION_KEYWORDS,
            ExpenseCategory.INVESTMENT: cls.INVESTMENT_KEYWORDS,
            ExpenseCategory.OTHER: cls.OTHER_KEYWORDS,
        }


class IncomeKeywordDatabase:
    """Keywords untuk 5 income types di Finance Tracker"""

    SALARY_KEYWORDS: Set[str] = frozenset({
        'gaji', 'salary', 'payroll', 'take home pay', 'monthly salary',
        'gaji bulanan', 'thr', 'tunjangan hari raya', 'bonus gaji',
    })

    FREELANCE_KEYWORDS: Set[str] = frozenset({
        'freelance', 'freelancer', 'project fee', 'consultation fee',
        'design fee', 'programming fee', 'upah proyek', 'jasa',
    })

    INVESTMENT_KEYWORDS: Set[str] = frozenset({
        'dividend', 'dividen', 'capital gain', 'interest', 'bunga',
        'deposit interest', 'reksadana', 'mutual fund return',
    })

    SIDE_HUSTLE_KEYWORDS: Set[str] = frozenset({
        'side hustle', 'sampingan', 'part time', 'bisnis sampingan',
        'dropship', 'reseller', 'affiliate', 'komisi',
    })

    OTHER_KEYWORDS: Set[str] = frozenset({
        'gift', 'hadiah', 'hibah', 'scholarship', 'beasiswa',
        'grant', 'reimbursement', 'refund', 'prize',
    })

    TRANSFER_KEYWORDS: Set[str] = frozenset({
        'transfer', 'trf', 'bank transfer', 'transfer masuk', 'transfer dari',
        'transfer received', 'remit', 'pindah buku', 'top up', 'topup',
        'incoming transfer', 'dana masuk',
    })

    @classmethod
    def get_all_keywords(cls) -> Dict[IncomeCategory, Set[str]]:
        return {
            IncomeCategory.SALARY: cls.SALARY_KEYWORDS,
            IncomeCategory.FREELANCE: cls.FREELANCE_KEYWORDS,
            IncomeCategory.INVESTMENT: cls.INVESTMENT_KEYWORDS,
            IncomeCategory.SIDE_HUSTLE: cls.SIDE_HUSTLE_KEYWORDS,
            IncomeCategory.TRANSFER: cls.TRANSFER_KEYWORDS,
            IncomeCategory.OTHER: cls.OTHER_KEYWORDS,
        }
