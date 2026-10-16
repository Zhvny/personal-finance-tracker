import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

def _expand_env(value):
    """Resolve ${ENV_VAR} placeholders in config.yaml from the environment."""
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value

@dataclass
class AppConfig:
    buy_threshold: float = 8.5
    wait_threshold: float = 6.0
    sl_atr_multiplier: float = 2.0
    tp_atr_multiplier: float = 4.0
    atr_gate: float = 0.05
    fetch_period: str = "1y"
    max_workers: int = 5
    fred_api_key: str = ""
    dxy_ticker: str = "DX-Y.NYB"
    security_enabled: bool = False
    access_token: str = ""
    allowed_ips: list = field(default_factory=list)
    ip_whitelist_enabled: bool = False
    commodity_tickers: list = field(default_factory=lambda: ["ADRO.JK", "PTBA.JK", "ITMG.JK", "MEDC.JK", "GOLD", "CL=F"])
    macro_refresh_hours: int = 24
    weights: dict = field(default_factory=lambda: {
        "trend": 0.30, "momentum": 0.30,
        "volatility": 0.20, "liquidity": 0.20
    })

    # Portfolio Optimization Constraints (Legacy/General)
    min_assets: int = 3
    max_assets: int = 7
    concentration_tolerance: float = 0.4
    sparsity_penalty: float = 0.05

    # Genetic Algorithm Parameters
    ga_pop_size: int = 50
    ga_generations: int = 100
    ga_mutation_rate: float = 0.1
    ga_max_assets: int = 7
    ga_sparsity_penalty: float = 0.05
    ga_concentration_tolerance: float = 0.15

    @classmethod
    def load(cls, path: str = None) -> "AppConfig":
        if path is None:
            # Try to find it relative to this file's parent's parent (stock_analyzer root)
            _BASE = Path(__file__).resolve().parent.parent
            path = str(_BASE / "config.yaml")

        if not os.path.exists(path): return cls()
        try:
            with open(path, "r") as f: d = yaml.safe_load(f)
            d = _expand_env(d)
            sec = d.get('security', {})
            opt = d.get('optimization', {})
            ga = d.get('ga', {})
            mac = d.get('macro', {})

            return cls(
                buy_threshold=d['scoring']['buy_threshold'],
                wait_threshold=d['scoring']['wait_threshold'],
                sl_atr_multiplier=d['signal']['sl_atr_multiplier'],
                tp_atr_multiplier=d['signal']['tp_atr_multiplier'],
                atr_gate=d['signal']['atr_high_risk_gate'],
                fetch_period=d['fetch']['period'],
                max_workers=d['fetch']['max_workers'],
                fred_api_key=d.get('fred', {}).get('api_key', "").strip(),
                dxy_ticker=mac.get('dxy_ticker', "DX-Y.NYB"),
                security_enabled=sec.get('enabled', False),
                access_token=sec.get('access_token', ""),
                allowed_ips=sec.get('allowed_ips', []),
                ip_whitelist_enabled=sec.get('enable_ip_whitelist', False),
                commodity_tickers=d.get('commodity_tickers', ["ADRO.JK", "PTBA.JK", "ITMG.JK", "MEDC.JK", "GOLD", "CL=F"]),
                macro_refresh_hours=d.get('fred', {}).get('refresh_hours', 24),
                weights=d['scoring'].get('weights', {"trend": 0.30, "momentum": 0.30, "volatility": 0.20, "liquidity": 0.20}),

                # New fields with safe fallbacks
                min_assets=opt.get('min_assets', 3),
                max_assets=opt.get('max_assets', 7),
                concentration_tolerance=opt.get('concentration_tolerance', 0.4),
                sparsity_penalty=opt.get('sparsity_penalty', 0.05),
                ga_pop_size=ga.get('pop_size', 50),
                ga_generations=ga.get('generations', 100),
                ga_mutation_rate=ga.get('mutation_rate', 0.1),
                ga_max_assets=ga.get('max_assets', 7),
                ga_sparsity_penalty=ga.get('sparsity_penalty', 0.05),
                ga_concentration_tolerance=ga.get('concentration_tolerance', 0.15)
            )
        except: return cls()
