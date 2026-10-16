from dataclasses import dataclass


@dataclass
class PredictionResult:
    ticker: str
    category: str
    global_acc: float
    precision_buy: float
    precision_sell: float
    n_sniper_buy: int
    n_sniper_sell: int
    latest_signal: str
    p_sell: float
    p_neutral: float
    p_buy: float
    timestamp: str
    random_acc: float = 0.333

    # BACKWARD COMPATIBILITY SHIMS
    @property
    def precision_high_conf(self) -> float:
        return max(self.precision_buy, self.precision_sell)

    @property
    def n_selective_signals(self) -> int:
        return self.n_sniper_buy + self.n_sniper_sell

    @property
    def latest_prob(self) -> float:
        sig = self.latest_signal.upper()
        if "BUY" in sig: return self.p_buy
        if "SELL" in sig: return self.p_sell
        return max(self.p_buy, self.p_sell, self.p_neutral)

@dataclass
class FeatureSet:
    ticker: str
    data: any  # DataFrame
