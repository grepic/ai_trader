"""Tests for named trading strategies."""

import pytest
from datetime import datetime, timezone

from app.schemas.core import AISignalOut
from app.services.strategy.strategies import evaluate_strategies, STRATEGIES


def make_signal(
    ticker="AAPL",
    confidence=85.0,
    trade_decision="BUY",
    risk_level="medium",
    event_type="earnings",
    sentiment="positive",
    expected_price_impact="medium",
    expected_time_horizon="hours",
    sources_used=None,
) -> AISignalOut:
    return AISignalOut(
        id="sig-001",
        ticker=ticker,
        event_summary="Test signal",
        event_type=event_type,
        sentiment=sentiment,
        confidence=confidence,
        expected_time_horizon=expected_time_horizon,
        expected_price_impact=expected_price_impact,
        risk_level=risk_level,
        trade_decision=trade_decision,
        reasoning_summary="Test reasoning",
        sources_used=sources_used or ["Reuters"],
        model_used="test-model",
        created_at=datetime.now(timezone.utc),
    )


class TestNewsMomentumStrategy:
    def test_high_impact_buy_approved(self):
        signal = make_signal(event_type="other", expected_price_impact="high")
        decision = evaluate_strategies(signal, ["news_momentum"])
        assert decision.should_trade is True
        assert decision.action == "BUY"

    def test_low_impact_blocked(self):
        signal = make_signal(event_type="other", expected_price_impact="low")
        decision = evaluate_strategies(signal, ["news_momentum"])
        assert decision.should_trade is False

    def test_minutes_horizon_blocked(self):
        signal = make_signal(event_type="other", expected_time_horizon="minutes", expected_price_impact="high")
        decision = evaluate_strategies(signal, ["news_momentum"])
        assert decision.should_trade is False

    def test_hold_signal_blocked(self):
        signal = make_signal(trade_decision="HOLD", expected_price_impact="high")
        decision = evaluate_strategies(signal, ["news_momentum"])
        assert decision.should_trade is False

    def test_high_impact_has_larger_size_multiplier(self):
        med = make_signal(event_type="other", expected_price_impact="medium")
        high = make_signal(event_type="other", expected_price_impact="high")
        dec_med = evaluate_strategies(med, ["news_momentum"])
        dec_high = evaluate_strategies(high, ["news_momentum"])
        assert dec_high.size_multiplier >= dec_med.size_multiplier


class TestEarningsSurpriseStrategy:
    def test_earnings_high_confidence_approved(self):
        signal = make_signal(event_type="earnings", confidence=90.0)
        decision = evaluate_strategies(signal, ["earnings_surprise"])
        assert decision.should_trade is True

    def test_non_earnings_blocked(self):
        signal = make_signal(event_type="other", confidence=90.0)
        decision = evaluate_strategies(signal, ["earnings_surprise"])
        assert decision.should_trade is False

    def test_earnings_low_confidence_blocked(self):
        signal = make_signal(event_type="earnings", confidence=70.0)
        decision = evaluate_strategies(signal, ["earnings_surprise"])
        assert decision.should_trade is False

    def test_sec_filing_approved(self):
        signal = make_signal(event_type="sec_filing", confidence=90.0)
        decision = evaluate_strategies(signal, ["earnings_surprise"])
        assert decision.should_trade is True

    def test_earnings_hold_signal_not_traded(self):
        signal = make_signal(event_type="earnings", confidence=90.0, trade_decision="HOLD")
        decision = evaluate_strategies(signal, ["earnings_surprise"])
        # Earnings HOLD => strategy declines to trade, evaluate_strategies returns ALERT_ONLY
        assert decision.should_trade is False
        assert decision.action == "ALERT_ONLY"


class TestSocialRumorStrategy:
    def test_rumor_always_alert_only(self):
        signal = make_signal(
            event_type="rumor",
            sources_used=["twitter", "reddit"],
            confidence=90.0,
        )
        decision = evaluate_strategies(signal, ["social_rumor_alert"])
        assert decision.should_trade is False
        assert decision.action == "ALERT_ONLY"


class TestConservativeStrategy:
    def test_sec_very_high_confidence_approved(self):
        signal = make_signal(event_type="sec_filing", confidence=95.0, risk_level="low")
        decision = evaluate_strategies(signal, ["conservative"])
        assert decision.should_trade is True
        assert decision.size_multiplier == 0.5  # Conservative sizing

    def test_high_risk_blocked_even_with_high_confidence(self):
        signal = make_signal(event_type="sec_filing", confidence=95.0, risk_level="high")
        decision = evaluate_strategies(signal, ["conservative"])
        assert decision.should_trade is False

    def test_non_sec_blocked(self):
        signal = make_signal(event_type="analyst_rating", confidence=95.0, risk_level="low")
        decision = evaluate_strategies(signal, ["conservative"])
        assert decision.should_trade is False


class TestMultipleStrategies:
    def test_first_winning_strategy_wins(self):
        signal = make_signal(event_type="other", expected_price_impact="high", confidence=90.0)
        # news_momentum will approve it, earnings_surprise won't (not earnings)
        decision = evaluate_strategies(signal, ["news_momentum", "earnings_surprise"])
        assert decision.should_trade is True
        assert "news_momentum" in decision.reason

    def test_all_decline_returns_alert_only(self):
        signal = make_signal(
            event_type="other",
            expected_price_impact="low",  # blocks news_momentum
            confidence=70.0,              # blocks earnings_surprise
        )
        decision = evaluate_strategies(signal, ["news_momentum", "earnings_surprise"])
        assert decision.should_trade is False
        assert decision.action == "ALERT_ONLY"

    def test_unknown_strategy_name_skipped(self):
        signal = make_signal(event_type="earnings", confidence=90.0)
        # Should still work with unknown strategy in the list
        decision = evaluate_strategies(signal, ["nonexistent_strategy", "earnings_surprise"])
        assert decision.should_trade is True
