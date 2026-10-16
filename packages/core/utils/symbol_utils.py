import re


class SymbolFormatter:
    """
    Centralized utility for normalizing ticker symbols across different markets.
    Copied and adapted for packages.core.
    """

    ALIASES = {
        "GOLD": "GC=F",
        "SILVER": "SI=F",
        "OIL": "CL=F",
        "XAU": "GC=F",
        "XAG": "SI=F",
        "PL": "PL=F",
        "HG": "HG=F",
        "BTC": "BTC-USD",
        "ETH": "ETH-USD",
        "MATIC": "POL-USD",
        "MATIC-USD": "POL-USD"
    }

    @staticmethod
    def get_market(symbol: str) -> str:
        s = symbol.upper().strip().replace("$", "")

        # 1. Explicit markers (Highest Priority)
        if s.endswith("-USD"):
            return "CRYPTO"
        if s.endswith(".JK") or s == "^JKSE":
            return "IDX"
        if "=F" in s:
            return "COMMODITIES"
        if "=X" in s:
            return "FOREX"

        # 2. Commodities Aliases
        if s in ["GOLD", "SILVER", "OIL", "XAU", "XAG", "PL", "HG"]:
            return "COMMODITIES"

        # 3. Whitelist heuristics for bare symbols (High Priority)
        CRYPTO_SYMBOLS = {
            "BTC", "ETH", "SOL", "XRP", "ADA", "BNB", "DOGE", "AVAX", "DOT", "POL",
            "LINK", "UNI", "ATOM", "LTC", "BCH", "ALGO", "XLM", "FIL", "NEAR", "APT",
            "ARB", "OP", "INJ", "SUI", "SEI", "TIA", "PYTH", "JUP", "WIF", "BONK",
            "STX", "ORDI", "ICP", "ETC", "HBAR", "IMX", "VET", "KAS", "TAO", "RNDR",
            "RUNE", "EGLD", "LDO", "FET", "TRX", "TON", "SHIB", "PEPE", "FLOKI",
            "KAVA", "GALA", "LUNA", "AAVE", "MKR", "COMP", "SNX", "CRV", "YFI",
            "SUSHI", "MANA", "SAND", "ENJ", "AXS", "ILV", "DYDX", "JOE", "PENDLE",
            "ENA", "W", "CORE", "SATS", "MNT", "BEAM", "PRIME", "DYM", "ALT",
            "MANTA", "ZETA", "BGB", "FLR", "KSM", "NEO", "THETA", "EOS", "BSV",
            "FLOW", "CAKE", "CHZ", "KCS", "FTM", "GRT", "GNO", "ZIL", "BAT",
            "NOT", "BRETT", "POPCAT"
        }
        if s in CRYPTO_SYMBOLS:
            return "CRYPTO"

        # 4. Catch SYMBOLUSD or SYMBOLUSDT
        if (s.endswith("USD") or s.endswith("USDT")) and len(s) > 3:
            base = s.replace("USDT", "").replace("USD", "").replace("-", "")
            if base in CRYPTO_SYMBOLS or len(base) <= 5: # Aggressive crypto detection
                return "CRYPTO"
        # Usually 6 chars like EURUSD or ends with =X (handled above)
        FOREX_CURRENCIES = {"IDR", "USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CHF", "NZD", "SGD"}
        if len(s) == 6:
            base1, base2 = s[:3], s[3:]
            if base1 in FOREX_CURRENCIES and base2 in FOREX_CURRENCIES:
                return "FOREX"

        if any(x in s for x in ["IDR=X", "USDIDR", "EURUSD"]):
            return "FOREX"

        # 6. IDX Whitelist
        IDX_SYMBOLS = {
            "BBCA", "BBRI", "BMRI", "BBNI", "ADRO", "PTBA", "ITMG", "BUMI", "ASII", "UNTR",
            "SMGR", "INTP", "TLKM", "ISAT", "TOWR", "GOTO", "ICBP", "MYOR", "UNVR", "GGRM",
            "AKRA", "BRIS", "INKP", "BRPT", "TPIA", "BYAN", "BREN", "AMMN", "CUAN", "MDKA",
            "MIKA", "PGAS", "CPIN", "EXCL", "KLBF", "ANTM", "MEDC"
        }
        if s in IDX_SYMBOLS:
            return "IDX"

        return "US"

    @classmethod
    def normalize(cls, symbol: str, market: str = None) -> str:
        if not symbol:
            return ""

        s = symbol.upper().strip().replace("$", "")

        # Apply aliases first
        if s in cls.ALIASES:
            s = cls.ALIASES[s]

        if market is None:
            market = cls.get_market(s)

        market = market.upper()

        if market == "CRYPTO":
            if s.endswith("-USD"): return s
            # Remove USDT or USD suffix before appending -USD
            if s.endswith("USDT"): s = s[:-4]
            elif s.endswith("USD"): s = s[:-3]
            return f"{s}-USD"
        if market == "IDX":
            if s == "^JKSE": return s
            return s if s.endswith(".JK") else f"{s}.JK"
        if market == "FOREX":
            return s if s.endswith("=X") else f"{s}=X"
        if market == "COMMODITIES":
            if s in ["GOLD", "SILVER", "OIL"]: return cls.ALIASES[s]
            return s if s.endswith("=F") else f"{s}=F"

        return s

    @staticmethod
    def validate(symbol: str) -> bool:
        if not symbol:
            return False
        # Basic Yahoo Finance symbol validation: alphanumeric, -, ., ^, =
        return bool(re.match(r'^[A-Z0-9.\-^=]+$', symbol))
