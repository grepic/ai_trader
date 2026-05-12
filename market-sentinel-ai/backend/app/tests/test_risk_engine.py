"""Tests for the Risk Management Engine."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.services.risk.engine import RiskEngine
from app.schemas.core import AISignalOut


def make_signal(
    ticker="AAPL",
    confidence=85.0,
    trade_decision="BUY",
    risk_level="medium",
) -> AISignalOut:
    return AISignalOut(
        id="sig-001",
        ticker=ticker,
        event_summary="Test signal",
        event_type="earnings",
        sentiment="positive",
        confidence=confidence,
        expected_time_horizon="hours",
        expected_price_impact="medium",
        risk_level=risk_level,
        trade_decision=trade_decision,
        reasoning_summary="Test reasoning",
        sources_used=["test_source"],
        model_used="test-model",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def risk():
    return RiskEngine()


class TestEmergencyStop:
    def test_emergency_stop_blocks_all_trades(self, risk):
        risk.emergency_stop()
        status = risk.get_status()
        assert status["emergency_stopped"] is True
        assert status["bot_running"] is False

    @pytest.mark.asyncio
    async def test_emergency_stop_fails_risk_check(self, risk):
        risk.emergency_stop()
        signal = make_signal()
        result = await risk.check_trade(
            signal=signal,
            current_price=150.0,
            account_cash=10000.0,
            open_position_count=0,
            market_open=True,
        )
        assert result.passed is False
        assert "Emergency stop" in result.notes

    def test_cannot_resume_after_emergency_stop(self, risk):
        risk.emergency_stop()
        risk.resume()
        assert risk.get_status()["emergency_stopped"] is True


class TestManualPause:
    @pytest.mark.asyncio
    async def test_paused_bot_blocks_trades(self, risk):
        risk.pause()
        signal = make_signal()
        result = await risk.check_trade(
            signal=signal,
            current_price=150.0,
            account_cash=10000.0,
            open_position_count=0,
            market_open=True,
        )
        assert result.passed is False
        assert "paused" in result.notes.lower()

    @pytest.mark.asyncio
    async def test_resumed_bot_allows_trades(self, risk):
        risk.pause()
        risk.resume()
        signal = make_signal()
        result = await risk.check_trade(
            signal=signal,
            current_price=150.0,
            account_cash=10000.0,
            open_position_count=0,
            market_open=True,
        )
        assert result.passed is True


class TestDailyLossLimit:
    @pytest.mark.asyncio
    async def test_daily_loss_limit_blocks_trade(self, risk):
        # Simulate losing $60 (over the $50 default limit)
        risk.record_trade_result("AAPL", -60.0)
        signal = make_signal()
        result = await risk.check_trade(
            signal=signal,
            current_price=150.0,
            account_cash=10000.0,
            open_position_count=0,
            market_open=True,
        )
        assert result.passed is False
        assert "Daily loss limit" in result.notes

    @pytest.mark.asyncio
    async def test_within_daily_loss_limit_passes(self, risk):
        # Simulate losing $20 (under $50 limit)
        risk.record_trade_result("AAPL", -20.0)
        signal = make_signal()
        result = await risk.check_trade(
            signal=signal,
            current_price=150.0,
            account_cash=10000.0,
            open_position_count=0,
            market_open=True,
        )
        assert result.passed is True


class TestConfidenceThreshold:
    @pytest.mark.asyncio
    async def test_low_confidence_blocks_trade(self, risk):
        signal = make_signal(confidence=50.0)  # Below 80 default threshold
        result = await risk.check_trade(
            signal=signal,
            current_price=150.0,
            account_cash=10000.0,
            open_position_count=0,
            market_open=True,
        )
        assert result.passed is False
        assert "confidence" in result.notes.lower()

    @pytest.mark.asyncio
    async def test_high_confidence_passes(self, risk):
        signal = make_signal(confidence=90.0)
        result = await risk.check_trade(
            signal=signal,
            current_price=150.0,
            account_cash=10000.0,
            open_position_count=0,
            market_open=True,
        )
        assert result.passed is True


class TestMaxTradeSizeCalculation:
    @pytest.mark.asyncio
    async def test_trade_size_calculated_correctly(self, risk):
        signal = make_signal(confidence=90.0)
        result = await risk.check_trade(
            signal=signal,
            current_price=10.0,
            account_cash=1000.0,
            open_position_count=0,
            market_open=True,
        )
        assert result.passed is True
        assert result.suggested_quantity is not None
        # Max trade is min($25, 10% of $1000=$100) = $25 → 2.5 shares at $10
        expected_max = min(25.0, 1000.0 * 0.1)
        expected_qty = expected_max / 10.0
        assert abs(result.suggested_quantity - expected_qty) < 0.01

    @pytest.mark.asyncio
    async def test_penny_stock_blocked(self, risk):
        signal = make_signal(confidence=90.0)
        result = await risk.check_trade(
            signal=signal,
            current_price=0.50,  # Penny stock
            account_cash=10000.0,
            open_position_count=0,
            market_open=True,
        )
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_expensive_stock_with_low_cash_blocked(self, risk):
        signal = make_signal(confidence=90.0)
        result = await risk.check_trade(
            signal=signal,
            current_price=500.0,  # Expensive stock
            account_cash=10.0,    # Almost no cash
            open_position_count=0,
            market_open=True,
        )
        assert result.passed is False


class TestMaxPositions:
    @pytest.mark.asyncio
    async def test_max_positions_blocks_new_buy(self, risk):
        signal = make_signal(trade_decision="BUY")
        result = await risk.check_trade(
            signal=signal,
            current_price=50.0,
            account_cash=10000.0,
            open_position_count=5,  # At max (default 5)
            market_open=True,
        )
        assert result.passed is False
        assert "Max open positions" in result.notes


class TestMarketClosed:
    @pytest.mark.asyncio
    async def test_market_closed_blocks_trade(self, risk):
        signal = make_signal()
        result = await risk.check_trade(
            signal=signal,
            current_price=150.0,
            account_cash=10000.0,
            open_position_count=0,
            market_open=False,  # Market closed
        )
        assert result.passed is False
        assert "Market is closed" in result.notes


class TestExtremeRisk:
    @pytest.mark.asyncio
    async def test_extreme_risk_blocks_trade(self, risk):
        signal = make_signal(risk_level="extreme")
        result = await risk.check_trade(
            signal=signal,
            current_price=150.0,
            account_cash=10000.0,
            open_position_count=0,
            market_open=True,
        )
        assert result.passed is False
        assert "EXTREME" in result.notes


class TestCooldown:
    @pytest.mark.asyncio
    async def test_cooldown_blocks_rapid_trades(self, risk):
        risk.set_cooldown("AAPL", seconds=3600)  # 1 hour cooldown
        signal = make_signal(ticker="AAPL")
        result = await risk.check_trade(
            signal=signal,
            current_price=150.0,
            account_cash=10000.0,
            open_position_count=0,
            market_open=True,
        )
        assert result.passed is False
        assert "cooldown" in result.notes.lower()
