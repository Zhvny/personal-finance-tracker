# apps/cli/investment_tracker/services/ai_strategy.py

PROMPT_TEMPLATE = """
You are a senior financial analyst. Analyze the following news headlines for {ticker} 
and determine the overall market sentiment.

Headlines:
{headlines}

Provide a sentiment polarity score between -1.0 (extremely bearish) and 1.0 (extremely bullish).
Identify key drivers (positive factors) and risks (negative factors).

Your response MUST be a valid JSON object with the EXACT following structure:
{{
    "score": float,
    "sentiment": "Bullish" | "Neutral" | "Bearish",
    "drivers": ["driver1", "driver2"],
    "risks": ["risk1", "risk2"],
    "summary": "A concise summary of why you chose this score."
}}
"""
