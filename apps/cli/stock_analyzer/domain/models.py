from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TradingSignal(Enum):
    STRONG_BUY = 'STRONG BUY'
    BUY = 'BUY'
    ACCUMULATE = 'ACCUMULATE'
    WAIT = 'WAIT'
    AVOID = 'AVOID'
    SELL = 'SELL'
    STRONG_SELL = 'STRONG SELL'

@dataclass
class StockResult:
    ticker: str
    score: float
    css: float = 0.0
    css_tier: str = 'NO_TRADE'
    vol_regime: str = 'NORMAL'
    macro_regime: str = 'NEUTRAL'
    is_commodity: bool = False
    trend_score: float = 0.0
    momentum_score: float = 0.0
    volatility_score: float = 0.0
    liquidity_score: float = 0.0
    signal: TradingSignal = TradingSignal.AVOID
    current_price: float = 0.0
    prev_close: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    support: float = 0.0
    resistance: float = 0.0
    forecast_1w: float = 0.0
    forecast_1m: float = 0.0
    target_price: float = 0.0
    dcds: float = None
    mrzg: str = 'NONE'
    csi: float = 0.0

    ml_signal: str = 'NEUTRAL'
    ml_prob: float = 0.5
    is_selective: bool = False
    n_sniper_buy: int = 0
    global_acc: float = 0.0
    precision: float = 0.0

    expectancy: float = 0.0
    kelly_fraction: float = 0.0
    position_size: float = 0.0
    win_rate: float = 0.0
    risk_reward_ratio: float = 0.0

    is_favorite: bool = False
    sparkline: list[float] = field(default_factory=list)

    # Advanced Strategies
    poc: float = 0.0
    vah: float = 0.0
    val: float = 0.0
    amt_state: str = 'NONE'
    market_structure: str = 'NEUTRAL'
    cumulative_delta: float = 0.0
    fvg_present: bool = False
    vwap: float = 0.0
    footprint_data: any = None
    profile_summary: list = field(default_factory=list)
    absorption_zones: list[float] = field(default_factory=list)

    timestamp: datetime = field(default_factory=datetime.now)
