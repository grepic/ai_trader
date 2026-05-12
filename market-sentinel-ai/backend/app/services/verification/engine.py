"""Source Verification Engine — scores every news item before it can trigger a trade."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Credibility tiers (0-100)
_SOURCE_CREDIBILITY: dict[str, float] = {
    # Official / Regulatory — highest trust
    "sec": 99,
    "sec.gov": 99,
    "edgar": 99,
    "investor_relations": 95,
    # Major wire services
    "reuters": 90,
    "bloomberg": 90,
    "associated_press": 88,
    "ap": 88,
    "dow_jones": 85,
    "wsj": 85,
    "wall_street_journal": 85,
    "financial_times": 83,
    "ft": 83,
    # Quality financial media
    "cnbc": 78,
    "marketwatch": 75,
    "barrons": 78,
    "seeking_alpha": 60,
    "benzinga": 65,
    "thestreet": 62,
    "motley_fool": 55,
    # Earnings / Data providers
    "earnings_whispers": 80,
    "estimize": 72,
    "alpha_vantage": 80,
    # Social — medium/low trust
    "twitter": 35,
    "x": 35,
    "reddit": 30,
    "stocktwits": 40,
    "telegram": 20,
    # Fallback
    "unknown": 20,
}

# Source types that require 2+ independent sources before trading
_REQUIRES_CORROBORATION = {"social", "rumor", "blog", "unknown"}

# Source types that are self-sufficient for trading
_HIGH_TRUST_TYPES = {"sec", "official"}


@dataclass
class VerificationResult:
    ticker: str
    credibility_score: float
    corroboration_score: float
    duplicate_story_score: float
    market_reaction_score: float
    final_confidence_score: float
    recommended_action: str  # TRADE_ALLOWED | ALERT_ONLY | IGNORE
    sentiment: str
    event_type: str
    verification_notes: str
    corroborating_source_ids: list[str] = field(default_factory=list)


class VerificationEngine:
    """
    Scores source items on credibility, corroboration, and deduplication
    before they can trigger a trade decision.
    """

    def __init__(self) -> None:
        self._seen_hashes: dict[str, list[str]] = {}  # dedup_hash -> [source_ids]

    def compute_dedup_hash(self, headline: str, ticker: str) -> str:
        """Content-based hash for deduplication."""
        normalized = re.sub(r"[^a-zA-Z0-9 ]", "", (headline or "").lower())
        words = sorted(set(normalized.split()))[:10]
        key = ticker.upper() + "|" + " ".join(words)
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def get_credibility_score(self, source_name: str, source_type: str) -> float:
        """Return credibility score 0-100 for a given source."""
        name_lower = source_name.lower().replace(" ", "_")
        type_lower = source_type.lower()

        # Check source type first (highest priority)
        if type_lower in _HIGH_TRUST_TYPES:
            return 99.0
        if type_lower == "sec":
            return 99.0

        # Check by name
        for key, score in _SOURCE_CREDIBILITY.items():
            if key in name_lower:
                return float(score)

        # Check by type
        type_scores = {
            "news": 65.0,
            "earnings": 80.0,
            "price": 95.0,
            "social": 30.0,
            "macro": 70.0,
        }
        return type_scores.get(type_lower, 25.0)

    def detect_sentiment(self, text: str) -> str:
        """Simple keyword-based sentiment detection."""
        text_lower = (text or "").lower()

        positive_words = [
            "beat", "beats", "exceeded", "exceeds", "surge", "surges", "record",
            "growth", "profit", "upgrade", "buy", "bullish", "positive", "strong",
            "rally", "gain", "increased", "approved", "partnership", "deal",
            "dividend", "acquisition", "merger", "buyback",
        ]
        negative_words = [
            "miss", "misses", "missed", "below", "decline", "loss", "losses",
            "downgrade", "sell", "bearish", "negative", "weak", "cut", "recall",
            "lawsuit", "investigation", "fine", "penalty", "fraud", "bankrupt",
            "layoff", "layoffs", "deficit", "shortfall", "disappointing",
        ]

        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)

        if pos_count > neg_count * 1.5:
            return "positive"
        if neg_count > pos_count * 1.5:
            return "negative"
        if pos_count > 0 and neg_count > 0:
            return "mixed"
        return "neutral"

    def detect_event_type(self, text: str, source_type: str) -> str:
        """Classify the event type from content."""
        text_lower = (text or "").lower()

        if source_type == "sec":
            return "sec_filing"

        patterns = {
            "earnings": ["earnings", "eps", "revenue", "quarterly", "q1", "q2", "q3", "q4", "guidance"],
            "merger": ["merger", "acquisition", "acquire", "takeover", "buyout", "deal"],
            "analyst_rating": ["upgrade", "downgrade", "price target", "outperform", "underperform", "buy rating"],
            "lawsuit": ["lawsuit", "sued", "litigation", "legal", "court", "investigation", "sec probe"],
            "ceo_change": ["ceo", "chief executive", "resigned", "appointed", "departure", "executive"],
            "product_launch": ["launch", "unveiled", "announced", "new product", "release"],
            "macro": ["fed", "federal reserve", "interest rate", "inflation", "gdp", "jobs report"],
            "political": ["tariff", "trade war", "regulation", "congress", "white house", "executive order"],
            "rumor": ["rumor", "reportedly", "sources say", "could be", "may be", "speculation"],
        }

        for event_type, keywords in patterns.items():
            if any(kw in text_lower for kw in keywords):
                return event_type

        return "other"

    def verify(
        self,
        source_id: str,
        source_name: str,
        source_type: str,
        ticker: str,
        headline: str,
        content: str | None,
        published_at: datetime | None,
        existing_hashes: dict[str, list[str]] | None = None,
    ) -> VerificationResult:
        """
        Score a source item and return a verification result.

        existing_hashes: dedup_hash -> [source_ids] from recently processed items
                         used to detect and count independent corroborating sources.
        """
        full_text = f"{headline} {content or ''}"
        dedup_hash = self.compute_dedup_hash(headline, ticker)
        sentiment = self.detect_sentiment(full_text)
        event_type = self.detect_event_type(full_text, source_type)

        # 1. Credibility score
        credibility = self.get_credibility_score(source_name, source_type)

        # 2. Corroboration — count independent sources for same story
        all_hashes = existing_hashes or self._seen_hashes
        corroborating_ids: list[str] = []
        if dedup_hash in all_hashes:
            # Filter to sources different from this one
            corroborating_ids = [s for s in all_hashes[dedup_hash] if s != source_id]

        # Update our dedup registry
        if dedup_hash not in self._seen_hashes:
            self._seen_hashes[dedup_hash] = []
        if source_id not in self._seen_hashes[dedup_hash]:
            self._seen_hashes[dedup_hash].append(source_id)

        # Score corroboration: each additional unique credible source adds points
        # But re-tweets / reposts of same content don't count as independent
        corroboration_score = min(100.0, len(corroborating_ids) * 25.0)

        # 3. Duplicate story penalty (if many reposts, we penalize the score)
        duplicate_penalty = min(20.0, max(0, len(corroborating_ids) - 4) * 5.0)
        duplicate_story_score = max(0, 100.0 - duplicate_penalty)

        # 4. Freshness / market reaction score
        market_reaction_score = 50.0
        if published_at:
            age = datetime.now(timezone.utc) - published_at.replace(
                tzinfo=timezone.utc if published_at.tzinfo is None else published_at.tzinfo
            )
            if age < timedelta(minutes=15):
                market_reaction_score = 90.0  # Very fresh
            elif age < timedelta(hours=1):
                market_reaction_score = 70.0
            elif age < timedelta(hours=4):
                market_reaction_score = 50.0
            else:
                market_reaction_score = 20.0  # Stale

        # 5. Final confidence score (weighted average)
        final_confidence = (
            credibility * 0.40
            + corroboration_score * 0.30
            + market_reaction_score * 0.20
            + duplicate_story_score * 0.10
        )

        # 6. Determine recommended action
        notes_parts = []
        is_high_trust = source_type.lower() in _HIGH_TRUST_TYPES or source_type.lower() == "sec"
        needs_corroboration = source_type.lower() in _REQUIRES_CORROBORATION

        if is_high_trust:
            recommended_action = "TRADE_ALLOWED"
            notes_parts.append(f"High-trust source type: {source_type}")
        elif needs_corroboration and len(corroborating_ids) < 1:
            recommended_action = "ALERT_ONLY"
            notes_parts.append(
                f"Source type '{source_type}' requires independent corroboration — none found yet"
            )
        elif final_confidence >= 70 and credibility >= 65:
            recommended_action = "TRADE_ALLOWED"
            notes_parts.append(f"Confidence {final_confidence:.1f} meets threshold")
        elif final_confidence >= 40:
            recommended_action = "ALERT_ONLY"
            notes_parts.append(f"Confidence {final_confidence:.1f} — alert only")
        else:
            recommended_action = "IGNORE"
            notes_parts.append(f"Confidence {final_confidence:.1f} too low")

        if corroborating_ids:
            notes_parts.append(f"{len(corroborating_ids)} corroborating source(s) found")

        return VerificationResult(
            ticker=ticker,
            credibility_score=round(credibility, 1),
            corroboration_score=round(corroboration_score, 1),
            duplicate_story_score=round(duplicate_story_score, 1),
            market_reaction_score=round(market_reaction_score, 1),
            final_confidence_score=round(final_confidence, 1),
            recommended_action=recommended_action,
            sentiment=sentiment,
            event_type=event_type,
            verification_notes="; ".join(notes_parts),
            corroborating_source_ids=corroborating_ids,
        )
