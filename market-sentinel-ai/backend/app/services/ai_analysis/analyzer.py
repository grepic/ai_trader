"""AI Analysis Engine — sends verified events to LLM and parses structured signals."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a professional quantitative financial analyst AI assistant for Market Sentinel AI.

Your task is to analyze financial news events and produce structured trading signals.

You MUST respond ONLY with a valid JSON object. No explanation text outside the JSON.

The JSON must have exactly these fields:
{
  "ticker": "TICKER",
  "event_summary": "Brief description of the event",
  "event_type": "earnings|lawsuit|ceo_change|product_launch|merger|macro|political|analyst_rating|rumor|regulatory|other",
  "sentiment": "positive|negative|neutral|mixed",
  "confidence": <0-100 integer>,
  "expected_time_horizon": "minutes|hours|days|weeks",
  "expected_price_impact": "low|medium|high",
  "risk_level": "low|medium|high|extreme",
  "trade_decision": "BUY|SELL|SHORT|COVER|HOLD|ALERT_ONLY|IGNORE",
  "reasoning_summary": "2-3 sentences explaining the signal",
  "sources_used": ["source1", "source2"]
}

Rules:
- confidence must be 0-100
- If the news is unverified rumor or single source, set confidence <= 50 and trade_decision = ALERT_ONLY
- If risk_level = extreme, always set trade_decision = ALERT_ONLY or IGNORE
- Be conservative. Prefer HOLD/ALERT_ONLY over BUY/SELL when uncertain
- Never recommend SHORT unless the signal is very strong and clearly negative
"""

_USER_TEMPLATE = """Analyze this financial event for trading signal generation:

TICKER: {ticker}
HEADLINE: {headline}
CONTENT: {content}
SOURCE TYPE: {source_type}
SOURCE NAME: {source_name}
PUBLISHED: {published_at}
SENTIMENT FROM VERIFICATION: {sentiment}
CONFIDENCE FROM VERIFICATION: {confidence_score}
CORROBORATING SOURCES: {corroboration_count}
EVENT TYPE HINT: {event_type}

Current market context:
- Is market open: {market_open}
- Source credibility: {credibility_score}/100

Generate the trading signal JSON:"""


class AIAnalyzer:
    """Wrapper around OpenAI-compatible API for financial signal generation."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def analyze(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze a verified event and return a structured signal dict.
        Falls back to a rule-based signal if the API call fails.
        """
        if not self._settings.has_openai:
            logger.warning("No OpenAI API key configured — using rule-based fallback")
            return self._rule_based_fallback(event_data)

        try:
            return await self._call_api(event_data)
        except Exception as e:
            logger.error("AI analysis failed: %s — using fallback", e)
            return self._rule_based_fallback(event_data)

    async def _call_api(self, event_data: dict[str, Any]) -> dict[str, Any]:
        import httpx

        prompt = _USER_TEMPLATE.format(
            ticker=event_data.get("ticker", "UNKNOWN"),
            headline=event_data.get("headline", "")[:500],
            content=(event_data.get("content", "") or "")[:1000],
            source_type=event_data.get("source_type", "unknown"),
            source_name=event_data.get("source_name", "unknown"),
            published_at=event_data.get("published_at", "unknown"),
            sentiment=event_data.get("sentiment", "neutral"),
            confidence_score=event_data.get("confidence_score", 0),
            corroboration_count=event_data.get("corroboration_count", 1),
            event_type=event_data.get("event_type", "other"),
            market_open=event_data.get("market_open", False),
            credibility_score=event_data.get("credibility_score", 50),
        )

        payload = {
            "model": self._settings.openai_model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 800,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._settings.openai_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        signal = json.loads(content)
        signal["model_used"] = self._settings.openai_model
        signal["raw_ai_response"] = data
        return self._validate_signal(signal, event_data)

    def _validate_signal(self, signal: dict[str, Any], event_data: dict[str, Any]) -> dict[str, Any]:
        """Sanitize and validate AI output fields."""
        valid_decisions = {"BUY", "SELL", "SHORT", "COVER", "HOLD", "ALERT_ONLY", "IGNORE"}
        valid_sentiments = {"positive", "negative", "neutral", "mixed"}
        valid_horizons = {"minutes", "hours", "days", "weeks"}
        valid_impacts = {"low", "medium", "high"}
        valid_risks = {"low", "medium", "high", "extreme"}

        signal.setdefault("ticker", event_data.get("ticker", "UNKNOWN"))
        signal.setdefault("event_summary", event_data.get("headline", "Unknown event"))
        signal.setdefault("event_type", event_data.get("event_type", "other"))

        if signal.get("sentiment") not in valid_sentiments:
            signal["sentiment"] = "neutral"
        if signal.get("trade_decision") not in valid_decisions:
            signal["trade_decision"] = "HOLD"
        if signal.get("expected_time_horizon") not in valid_horizons:
            signal["expected_time_horizon"] = "days"
        if signal.get("expected_price_impact") not in valid_impacts:
            signal["expected_price_impact"] = "low"
        if signal.get("risk_level") not in valid_risks:
            signal["risk_level"] = "medium"

        # Clamp confidence
        try:
            signal["confidence"] = max(0, min(100, float(signal.get("confidence", 50))))
        except (TypeError, ValueError):
            signal["confidence"] = 50.0

        # Safety: extreme risk => never allow direct trade
        if signal["risk_level"] == "extreme" and signal["trade_decision"] in ("BUY", "SELL", "SHORT"):
            signal["trade_decision"] = "ALERT_ONLY"
            signal["reasoning_summary"] = (
                "[Risk override] " + signal.get("reasoning_summary", "")
            )

        signal.setdefault("sources_used", [event_data.get("source_name", "unknown")])
        signal.setdefault("reasoning_summary", "AI analysis completed.")
        return signal

    def _rule_based_fallback(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """Deterministic signal when AI API is unavailable."""
        sentiment = event_data.get("sentiment", "neutral")
        confidence = float(event_data.get("confidence_score", 0))
        credibility = float(event_data.get("credibility_score", 0))
        source_type = event_data.get("source_type", "")

        # Basic rule: low credibility or confidence => alert only
        if credibility < 60 or confidence < 60:
            decision = "ALERT_ONLY"
            risk = "high"
        elif sentiment == "positive" and confidence >= 75:
            decision = "BUY"
            risk = "medium"
        elif sentiment == "negative" and confidence >= 75:
            decision = "SELL"
            risk = "medium"
        else:
            decision = "HOLD"
            risk = "medium"

        # SEC filings get elevated trust
        if source_type == "sec":
            risk = "low"

        return {
            "ticker": event_data.get("ticker", "UNKNOWN"),
            "event_summary": event_data.get("headline", "Financial event detected"),
            "event_type": event_data.get("event_type", "other"),
            "sentiment": sentiment,
            "confidence": confidence,
            "expected_time_horizon": "hours",
            "expected_price_impact": "medium" if confidence >= 70 else "low",
            "risk_level": risk,
            "trade_decision": decision,
            "reasoning_summary": (
                f"Rule-based signal (AI unavailable). Sentiment: {sentiment}, "
                f"confidence: {confidence:.0f}, credibility: {credibility:.0f}."
            ),
            "sources_used": [event_data.get("source_name", "unknown")],
            "model_used": "rule-based-fallback",
            "raw_ai_response": None,
        }
