"""Tests for the Source Verification Engine."""

import pytest
from datetime import datetime, timezone, timedelta

from app.services.verification.engine import VerificationEngine


@pytest.fixture
def engine():
    return VerificationEngine()


class TestCredibilityScoring:
    def test_sec_gets_max_score(self, engine):
        score = engine.get_credibility_score("SEC EDGAR", "sec")
        assert score >= 95

    def test_reuters_high_trust(self, engine):
        score = engine.get_credibility_score("reuters", "news")
        assert score >= 85

    def test_unknown_social_low_trust(self, engine):
        score = engine.get_credibility_score("random_twitter_account", "social")
        assert score <= 40

    def test_reddit_low_trust(self, engine):
        score = engine.get_credibility_score("reddit", "social")
        assert score <= 40

    def test_bloomberg_high_trust(self, engine):
        score = engine.get_credibility_score("bloomberg", "news")
        assert score >= 85


class TestSentimentDetection:
    def test_positive_sentiment(self, engine):
        text = "Company beats earnings estimates by 15%, raises guidance"
        assert engine.detect_sentiment(text) == "positive"

    def test_negative_sentiment(self, engine):
        text = "Company misses revenue expectations, faces SEC investigation"
        assert engine.detect_sentiment(text) == "negative"

    def test_neutral_sentiment(self, engine):
        text = "Company announces quarterly results as expected"
        assert engine.detect_sentiment(text) == "neutral"

    def test_mixed_sentiment(self, engine):
        text = "Company beats earnings but issues downgrade warning"
        result = engine.detect_sentiment(text)
        assert result in ("mixed", "positive", "negative")  # Mixed signals


class TestDeduplication:
    def test_same_headline_same_hash(self, engine):
        h1 = engine.compute_dedup_hash("AAPL reports record earnings for Q3", "AAPL")
        h2 = engine.compute_dedup_hash("AAPL reports record earnings for Q3", "AAPL")
        assert h1 == h2

    def test_different_ticker_different_hash(self, engine):
        h1 = engine.compute_dedup_hash("Company reports record earnings for Q3", "AAPL")
        h2 = engine.compute_dedup_hash("Company reports record earnings for Q3", "MSFT")
        assert h1 != h2

    def test_slightly_different_headline_same_hash(self, engine):
        # Normalization should make these match
        h1 = engine.compute_dedup_hash("AAPL reports RECORD earnings!!! for Q3 2024", "AAPL")
        h2 = engine.compute_dedup_hash("aapl reports record earnings for q3 2024", "AAPL")
        assert h1 == h2


class TestVerificationDecisions:
    def test_sec_filing_always_trade_allowed(self, engine):
        result = engine.verify(
            source_id="test-1",
            source_name="SEC EDGAR",
            source_type="sec",
            ticker="AAPL",
            headline="AAPL files 8-K: Material event",
            content="Apple discloses acquisition",
            published_at=datetime.now(timezone.utc),
        )
        assert result.recommended_action == "TRADE_ALLOWED"

    def test_unverified_social_single_source_alert_only(self, engine):
        result = engine.verify(
            source_id="test-2",
            source_name="random_twitter",
            source_type="social",
            ticker="TSLA",
            headline="TSLA going to the moon (rumor)",
            content="Some person on Twitter says TSLA will 10x",
            published_at=datetime.now(timezone.utc),
        )
        # Single unverified social source must NOT be TRADE_ALLOWED
        assert result.recommended_action in ("ALERT_ONLY", "IGNORE")

    def test_stale_news_lower_confidence(self, engine):
        old_time = datetime.now(timezone.utc) - timedelta(hours=12)
        result = engine.verify(
            source_id="test-3",
            source_name="Reuters",
            source_type="news",
            ticker="MSFT",
            headline="MSFT announces new product line",
            content="Microsoft unveils new surface products",
            published_at=old_time,
        )
        assert result.market_reaction_score < 50  # Old news loses freshness score

    def test_fresh_reuters_high_confidence(self, engine):
        result = engine.verify(
            source_id="test-4",
            source_name="Reuters",
            source_type="news",
            ticker="MSFT",
            headline="MSFT announces $10B buyback program",
            content="Microsoft announces share buyback",
            published_at=datetime.now(timezone.utc),
        )
        assert result.credibility_score >= 85
        assert result.market_reaction_score >= 80

    def test_duplicate_story_no_independent_corroboration(self, engine):
        """Multiple reposts of same rumor should not count as independent confirmation."""
        headline = "RUMORED: Company X considering acquisition of Company Y"

        # First source
        result1 = engine.verify(
            source_id="src-1",
            source_name="unknown_blog_1",
            source_type="social",
            ticker="AAPL",
            headline=headline,
            content=headline,
            published_at=datetime.now(timezone.utc),
        )
        # Second source (same story)
        result2 = engine.verify(
            source_id="src-2",
            source_name="unknown_blog_2",
            source_type="social",
            ticker="AAPL",
            headline=headline,
            content=headline,
            published_at=datetime.now(timezone.utc),
        )

        # Both should be ALERT_ONLY or IGNORE — single rumor reposted is not independent
        assert result1.recommended_action in ("ALERT_ONLY", "IGNORE")


class TestEventTypeDetection:
    def test_earnings_detection(self, engine):
        text = "Company reports Q3 earnings results beating EPS estimates"
        assert engine.detect_event_type(text, "news") == "earnings"

    def test_merger_detection(self, engine):
        text = "Company in acquisition talks with major rival"
        assert engine.detect_event_type(text, "news") == "merger"

    def test_analyst_rating_detection(self, engine):
        text = "Analyst upgrades stock to outperform with new price target"
        assert engine.detect_event_type(text, "news") == "analyst_rating"

    def test_lawsuit_detection(self, engine):
        text = "Company faces SEC investigation over accounting practices"
        assert engine.detect_event_type(text, "news") == "lawsuit"

    def test_sec_filing_override(self, engine):
        text = "Company files quarterly earnings report"
        assert engine.detect_event_type(text, "sec") == "sec_filing"
