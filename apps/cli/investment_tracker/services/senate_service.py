from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List

import numpy as np
import pandas as pd

from apps.cli.investment_tracker.services.butterfly_service import ButterflyService
from apps.cli.investment_tracker.services.sentiment_service import SentimentService

# Local imports — using absolute paths to be importable from any context (API server, CLI, tests)
from apps.cli.prediction_service import PredictionService


class Vote(Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"

@dataclass
class AgentOpinion:
    agent_name: str
    vote: Vote
    confidence: float
    rationale: str

@dataclass
class SenateResult:
    consensus: Vote
    confidence: float
    opinions: List[AgentOpinion]
    timestamp: datetime
    market_regime: str
    data_quality: str

class BaseAgent(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def vote(self, df: pd.DataFrame) -> AgentOpinion:
        """Each agent must return a Vote and a dynamic Rationale."""
        pass

class MomentumAgent(BaseAgent):
    def __init__(self):
        super().__init__("Momentum Agent")

    def vote(self, df: pd.DataFrame) -> AgentOpinion:
        close = df['Close']
        volume = df['Volume']
        ma20 = close.rolling(20).mean()
        rsi = self._calculate_rsi(close)

        last_close = close.iloc[-1]
        last_ma20 = ma20.iloc[-1]
        last_rsi = rsi.iloc[-1]

        vol_ma = volume.rolling(20).mean().iloc[-1]
        last_vol = volume.iloc[-1]
        vol_confirm = last_vol > vol_ma

        if last_close > last_ma20 and last_rsi > 55:
            conf = 0.7 if vol_confirm else 0.5
            msg = f"Upward momentum: RSI {last_rsi:.1f}, Price > MA20."
            if vol_confirm: msg += " Volume confirmed."
            return AgentOpinion(self.name, Vote.BUY, conf, msg)
        elif last_close < last_ma20 or last_rsi < 45:
            conf = 0.6 if vol_confirm else 0.4
            return AgentOpinion(self.name, Vote.SELL, conf, f"Bearish trend: Price < MA20 or RSI {last_rsi:.1f} weakened.")

        return AgentOpinion(self.name, Vote.HOLD, 0.5, "Momentum neutral.")

    def _calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-8)
        return 100 - (100 / (1 + rs))

class ValueAgent(BaseAgent):
    def __init__(self):
        super().__init__("Value Agent")

    def vote(self, df: pd.DataFrame) -> AgentOpinion:
        close = df['Close']
        ma200 = close.rolling(200).mean()
        if len(close) < 200:
            ma200 = close.rolling(min(len(close), 50)).mean()

        last_close = close.iloc[-1]
        last_ma200 = ma200.iloc[-1]
        rel_price = last_close / last_ma200

        if rel_price < 0.9:
            return AgentOpinion(self.name, Vote.BUY, 0.8, f"Undervalued: {((1-rel_price)*100):.1f}% below 200-day mean.")
        elif rel_price > 1.2:
            return AgentOpinion(self.name, Vote.SELL, 0.7, f"Overextended: {((rel_price-1)*100):.1f}% above 200-day mean.")
        return AgentOpinion(self.name, Vote.HOLD, 0.5, "Fair value range.")

class MacroAgent(BaseAgent):
    def __init__(self):
        super().__init__("Macro Agent")
        self.butterfly = ButterflyService()

    def vote(self, df: pd.DataFrame) -> AgentOpinion:
        ticker = getattr(df, 'ticker', 'UNKNOWN')
        risk_map = self.butterfly.get_risk_map(ticker, df)

        if not risk_map:
            return AgentOpinion(self.name, Vote.HOLD, 0.3, "Insufficient macro correlation data.")

        strongest = risk_map[0]
        if strongest.ticker == "GC=F" and strongest.correlation > 0.5:
            return AgentOpinion(self.name, Vote.BUY, 0.6, f"Macro hedge: High correlation ({strongest.correlation:.2f}) with Gold.")
        if strongest.ticker == "DX-Y.NYB" and strongest.correlation < -0.5:
             return AgentOpinion(self.name, Vote.BUY, 0.6, "Dollar inverse: Strong negative correlation with DXY.")

        return AgentOpinion(self.name, Vote.HOLD, 0.4, f"Macro environment neutral. Strongest driver: {strongest.description}.")

class MeanReversionAgent(BaseAgent):
    def __init__(self):
        super().__init__("Mean Reversion Agent")

    def vote(self, df: pd.DataFrame) -> AgentOpinion:
        close = df['Close']
        ma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        upper = ma20 + (2 * std20)
        lower = ma20 - (2 * std20)

        last_close = close.iloc[-1]

        if last_close < lower.iloc[-1]:
            return AgentOpinion(self.name, Vote.BUY, 0.7, "Oversold: Price below lower Bollinger Band.")
        elif last_close > upper.iloc[-1]:
            return AgentOpinion(self.name, Vote.SELL, 0.7, "Overbought: Price above upper Bollinger Band.")

        return AgentOpinion(self.name, Vote.HOLD, 0.5, "Price within normal distribution.")

class RiskAgent(BaseAgent):
    def __init__(self):
        super().__init__("Risk Agent")

    def vote(self, df: pd.DataFrame) -> AgentOpinion:
        high, low, close = df['High'], df['Low'], df['Close']
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        atr_pct = (atr.iloc[-1] / close.iloc[-1]) * 100

        if atr_pct > 5.0:
            return AgentOpinion(self.name, Vote.SELL, 0.9, f"Risk Alert: Extreme volatility ({atr_pct:.1f}% ATR).")
        return AgentOpinion(self.name, Vote.HOLD, 0.5, f"Volatility stable ({atr_pct:.1f}% ATR).")

class SentimentAgent(BaseAgent):
    def __init__(self):
        super().__init__("Sentiment Agent (LLM)")
        self.svc = SentimentService()

    def vote(self, df: pd.DataFrame) -> AgentOpinion:
        ticker = getattr(df, 'ticker', 'UNKNOWN')
        res = self.svc.analyze_ticker(ticker)
        v_map = {"Bullish": Vote.BUY, "Bearish": Vote.SELL, "Neutral": Vote.HOLD}
        return AgentOpinion(self.name, v_map.get(res.sentiment, Vote.HOLD), abs(res.score) or 0.5, res.summary)

class QuantitativeAgent(BaseAgent):
    """Bridge to the existing XGBoost PredictionService."""
    def __init__(self, category: str):
        super().__init__("Quant Agent (XGBoost)")
        self.category = category

    def vote(self, df: pd.DataFrame) -> AgentOpinion:
        ticker = getattr(df, 'ticker', 'UNKNOWN')
        res = PredictionService.get_prediction(ticker, self.category)

        if res.get('status') != 'success':
            status = res.get('status', 'unknown_error')
            msg = "No ML model available for this asset." if status == 'insufficient_data' else f"ML prediction error: {status}"
            return AgentOpinion(self.name, Vote.HOLD, 0.0, msg)

        pred = res['data']
        ret = pred['pred_return']
        conf = pred['confidence']

        if ret > 0.02 and conf > 0.6:
            return AgentOpinion(
                self.name,
                Vote.BUY,
                conf,
                f"ML model predicts {ret*100:+.1f}% return with {conf*100:.0f}% confidence based on optimized features."
            )
        elif ret < -0.02 and conf > 0.6:
            return AgentOpinion(
                self.name,
                Vote.SELL,
                conf,
                f"ML model predicts {ret*100:+.1f}% return with {conf*100:.0f}% confidence. Bearish signal."
            )
        return AgentOpinion(
            self.name,
            Vote.HOLD,
            0.4,
            f"ML prediction is neutral ({ret*100:+.1f}% return) with moderate confidence."
        )

class SenateService:
    def __init__(self, category: str):
        self.category = category
        self.agents: List[BaseAgent] = [
            MomentumAgent(), ValueAgent(), MacroAgent(),
            MeanReversionAgent(), RiskAgent(), SentimentAgent(),
            QuantitativeAgent(category)
        ]

    def _get_market_regime(self, df: pd.DataFrame) -> str:
        close = df['Close']
        if len(close) < 200:
            ma50 = close.rolling(min(len(close), 20)).mean().iloc[-1]
            ma200 = close.rolling(min(len(close), 50)).mean().iloc[-1]
        else:
            ma50 = close.rolling(50).mean().iloc[-1]
            ma200 = close.rolling(200).mean().iloc[-1]

        if ma50 > ma200: return "Bull"
        if ma50 < ma200: return "Bear"
        return "Sideways"

    def sigmoid(self, x, scaling=5.0):
        return 1 / (1 + np.exp(-x * scaling))

    def get_senate_decision(self, ticker: str, df: pd.DataFrame) -> SenateResult:
        df.ticker = ticker
        regime = self._get_market_regime(df)
        opinions = []

        # Load weights from DB (mocked for now, will use agent_performance later)
        weights = {
            "Momentum Agent": 1.2 if regime == "Bull" else 0.8,
            "Mean Reversion Agent": 1.2 if regime == "Sideways" else 0.8,
            "Risk Agent": 1.5 if regime == "Bear" else 1.0,
            "Value Agent": 1.0,
            "Macro Agent": 1.0,
            "Sentiment Agent (LLM)": 1.0,
            "Quant Agent (XGBoost)": 1.0
        }

        total_score = 0.0
        total_weight = 0.0
        total_conf_weighted = 0.0

        for agent in self.agents:
            try:
                op = agent.vote(df)
                opinions.append(op)

                # Consensus Math: BUY=+1, SELL=-1, HOLD=0
                val = 1.0 if op.vote == Vote.BUY else (-1.0 if op.vote == Vote.SELL else 0.0)
                w = weights.get(agent.name, 1.0)
                total_score += val * op.confidence * w
                total_weight += w
                total_conf_weighted += op.confidence * w
            except Exception as e:
                print(f"Agent {agent.name} failed: {e}")

        net_bias = total_score / (total_weight + 1e-8)

        if abs(net_bias) > 0.2:
            consensus = Vote.BUY if net_bias > 0 else Vote.SELL
            confidence = self.sigmoid(abs(net_bias))
        else:
            consensus = Vote.HOLD
            confidence = total_conf_weighted / (total_weight + 1e-8)

        # Data Integrity Check
        data_quality = "High"
        quality_issues = []
        for op in opinions:
            if "Sentiment Agent" in op.agent_name and ("mocked" in op.rationale.lower() or "error" in op.rationale.lower()):
                quality_issues.append("Mock/Error Sentiment")
            if "Macro Agent" in op.agent_name and "Insufficient macro correlation data" in op.rationale:
                quality_issues.append("Missing Macro Data")

        if quality_issues:
            data_quality = "Warning: " + ", ".join(quality_issues)

        result = SenateResult(
            consensus=consensus,
            confidence=confidence,
            opinions=opinions,
            timestamp=datetime.now(),
            market_regime=regime,
            data_quality=data_quality
        )

        current_price = float(df['Close'].iloc[-1])
        self._log_to_audit(ticker, result, weights, current_price)
        return result

    def _log_to_audit(self, ticker: str, result: SenateResult, weights: Dict, current_price: float = None):
        try:
            from apps.cli.investment_tracker.core.repository import DatabaseManager
            for op in result.opinions:
                sql = """
                    INSERT INTO audit.agent_predictions 
                    (agent_name, ticker, timeframe, prediction, confidence, reasoning, market_regime, orchestrator_weight, price_at_prediction)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                DatabaseManager.execute(sql, (
                    op.agent_name, ticker, "H24", op.vote.value, op.confidence,
                    op.rationale, result.market_regime, weights.get(op.agent_name, 1.0),
                    current_price
                ))
        except Exception as e:
            # Silent failure in prod, but print for dev
            print(f"Audit Log Failed: {e}")
