# apps/cli/investment_tracker/test_sentiment_integration.py
import os
import sys
from unittest.mock import MagicMock, patch

# Add the project root to sys.path to allow absolute imports like 'apps.cli...'
# Root is resolved dynamically
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from services.sentiment_service import SentimentService


def test_sentiment_logic():
    print("Testing SentimentService logic with mocked Gemini...")

    # Mock news
    mock_headlines = [
        "Apple reports record breaking earnings",
        "iPhone sales exceed expectations",
        "New AI features announced for Mac",
        "Dividend increased by 10%",
        "Analysts upgrade AAPL to Strong Buy"
    ]

    service = SentimentService(api_key="mock_key")

    # Mock the Gemini model response
    mock_response = MagicMock()
    mock_response.text = """
    {
        "score": 0.85,
        "sentiment": "Bullish",
        "drivers": ["Record earnings", "iPhone sales growth", "AI innovation"],
        "risks": ["Supply chain constraints"],
        "summary": "Extremely positive news cycle with strong financial performance and future catalysts."
    }
    """

    with patch('google.generativeai.GenerativeModel') as MockModel:
        instance = MockModel.return_value
        instance.generate_content.return_value = mock_response

        with patch.object(service, 'get_headlines', return_value=mock_headlines):
            result = service.analyze_ticker("AAPL")

            print(f"Ticker: {result.ticker}")
            print(f"Sentiment: {result.sentiment}")
            print(f"Score: {result.score}")
            print(f"Summary: {result.summary}")

            assert result.sentiment == "Bullish"
            assert result.score == 0.85
            assert "Record earnings" in result.drivers
            print("Test PASSED!")

if __name__ == "__main__":
    try:
        import google.generativeai
        test_sentiment_logic()
    except ImportError:
        print("google-generativeai not installed, skipping test.")
