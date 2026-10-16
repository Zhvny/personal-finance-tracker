import json
import os
from dataclasses import dataclass
from typing import List, Optional

import yfinance as yf

from apps.cli.investment_tracker.services.ai_strategy import PROMPT_TEMPLATE


@dataclass
class SentimentResult:
    ticker: str
    sentiment: str # Bullish, Neutral, Bearish
    score: float   # -1.0 to 1.0
    drivers: List[str]
    risks: List[str]
    summary: str

class SentimentService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._model = None

    def _get_model(self):
        if not self._model:
            import google.generativeai as genai
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY not found in environment or constructor.")
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel('gemini-1.5-flash')
        return self._model

    def analyze_ticker(self, ticker: str) -> SentimentResult:
        """
        Analyze sentiment for a ticker using Gemini Pro and Yahoo Finance news.
        """
        headlines = self.get_headlines(ticker)
        if not headlines:
            return SentimentResult(
                ticker=ticker,
                sentiment="Neutral",
                score=0.0,
                drivers=[],
                risks=[],
                summary="No recent news found to analyze."
            )

        headlines_str = "\n".join([f"- {h}" for h in headlines])
        prompt = PROMPT_TEMPLATE.format(ticker=ticker, headlines=headlines_str)

        try:
            model = self._get_model()
            response = model.generate_content(prompt)

            # Extract JSON from response (handling potential markdown wrapping)
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:-3].strip()
            elif text.startswith("```"):
                text = text[3:-3].strip()

            data = json.loads(text)

            return SentimentResult(
                ticker=ticker,
                sentiment=data.get("sentiment", "Neutral"),
                score=float(data.get("score", 0.0)),
                drivers=data.get("drivers", []),
                risks=data.get("risks", []),
                summary=data.get("summary", "Analysis completed.")
            )
        except Exception as e:
            print(f"Sentiment Analysis Error for {ticker}: {e}")
            return SentimentResult(
                ticker=ticker,
                sentiment="Neutral",
                score=0.0,
                drivers=[],
                risks=[],
                summary=f"Error during analysis: {str(e)}"
            )

    def get_headlines(self, ticker: str) -> List[str]:
        """Fetch last 5 news headlines from Yahoo Finance."""
        try:
            t = yf.Ticker(ticker)
            news = t.news
            if not news:
                return []

            headlines = []
            for n in news[:5]:
                # yfinance news structure: {'content': {'title': '...'}} or similar
                # We saw n['content']['title'] in our test
                title = n.get('content', {}).get('title') or n.get('title')
                if title:
                    headlines.append(title)
            return headlines
        except Exception as e:
            print(f"Error fetching news for {ticker}: {e}")
            return []
