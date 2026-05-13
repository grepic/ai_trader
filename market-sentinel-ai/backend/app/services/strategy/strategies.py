"""Named trading strategies — each defines its own signal filter and sizing rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.schemas.core import AISignalOut


@dataclass
class StrategyDecision:
    """Output of a strategy evaluation."""
    should_trade: bool
    action: str  # BUY | SELL | HOLD | ALERT_ONLY
    size_multiplier: float = 1.0  # Scale max_trade_size_usd by this factor
    reason: str = ""


def _news_momentum_strategy(signal: AISignalOut) -> StrategyDecision:
    """
    Trade confirmed news with strong momentum signals.
    Requires medium/high price impact and multi-hour horizon.
    """
    if signal.trade_decision not in ("BUY", "SELL"):
        return StrategyDecision(False, "HOLD", reason="Non-directional signal")

    if signal.expected_price_impact == "low":
        return StrategyDecision(False, "ALERT_ONLY", reason="Price impact too low for momentum trade")

    if signal.expected_time_horizon == "minutes":
        return StrategyDecision(False, "ALERT_ONLY", reason="Too short-lived for safe entry")

    size = 1.0 if signal.expected_price_impact == "medium" else 1.5
    return StrategyDecision(
        should_trade=True,
        action=signal.trade_decision,
        size_multiplier=size,
        reason=f"News momentum: {signal.sentiment} sentiment, {signal.expected_price_impact} impact",
    )


def _earnings_surprise_strategy(signal: AISignalOut) -> StrategyDecision:
    """
    Trade earnings beats/misses with high confidence.
    Only acts on earnings-type events with very high confidence.
    """
    if signal.event_type not in ("earnings", "sec_filing"):
        return StrategyDecision(False, "ALERT_ONLY", reason="Not an earnings event")

    if signal.confidence < 85:
        return StrategyDecision(False, "ALERT_ONLY", reason=f"Earnings confidence {signal.confidence:.0f}% < 85% threshold")

    if signal.trade_decision not in ("BUY", "SELL"):
        return StrategyDecision(False, "HOLD", reason="Earnings signal is neutral/mixed")

    return StrategyDecision(
        should_trade=True,
        action=signal.trade_decision,
        size_multiplier=1.2,
        reason=f"Earnings surprise: {signal.sentiment} with {signal.confidence:.0f}% confidence",
    )


def _analyst_rating_strategy(signal: AISignalOut) -> StrategyDecision:
    """
    Trade analyst upgrades/downgrades from credible sources.
    Requires high confidence and clear directional signal.
    """
    if signal.event_type != "analyst_rating":
        return StrategyDecision(False, "ALERT_ONLY", reason="Not an analyst rating event")

    if signal.confidence < 80:
        return StrategyDecision(False, "ALERT_ONLY", reason="Analyst confidence too low")

    return StrategyDecision(
        should_trade=True,
        action=signal.trade_decision if signal.trade_decision in ("BUY", "SELL") else "HOLD",
        size_multiplier=0.8,  # Conservative size for analyst trades
        reason=f"Analyst rating: {signal.sentiment}",
    )


def _social_rumor_strategy(signal: AISignalOut) -> StrategyDecision:
    """
    Social rumors are NEVER automatically traded — alert only.
    This strategy exists to explicitly classify social signals.
    """
    if signal.event_type == "rumor" or signal.sources_used and all(
        any(s in src.lower() for s in ["twitter", "reddit", "stocktwits", "social", "x.com"])
        for src in (signal.sources_used or [])
    ):
        return StrategyDecision(False, "ALERT_ONLY", reason="Social/rumor source — alert only, never auto-trade")

    return StrategyDecision(False, "ALERT_ONLY", reason="Social strategy: no auto-trade")


def _conservative_strategy(signal: AISignalOut) -> StrategyDecision:
    """
    Most conservative strategy — only trades SEC filings with very high confidence.
    Max size 50% of normal.
    """
    if signal.event_type not in ("sec_filing", "earnings") or signal.confidence < 90:
        return StrategyDecision(False, "ALERT_ONLY", reason="Conservative: requires SEC/earnings + 90% confidence")

    if signal.risk_level in ("high", "extreme"):
        return StrategyDecision(False, "ALERT_ONLY", reason="Conservative: risk level too high")

    return StrategyDecision(
        should_trade=True,
        action=signal.trade_decision if signal.trade_decision in ("BUY", "SELL") else "HOLD",
        size_multiplier=0.5,
        reason=f"Conservative SEC/earnings trade: {signal.confidence:.0f}% confidence",
    )


# Registry of named strategies
STRATEGIES: dict[str, Callable[[AISignalOut], StrategyDecision]] = {
    "news_momentum": _news_momentum_strategy,
    "earnings_surprise": _earnings_surprise_strategy,
    "analyst_rating": _analyst_rating_strategy,
    "social_rumor_alert": _social_rumor_strategy,
    "conservative": _conservative_strategy,
}

# Default active strategy set (all run in parallel; most permissive wins for BUY/SELL)
DEFAULT_ACTIVE_STRATEGIES = ["news_momentum", "earnings_surprise", "analyst_rating"]


def evaluate_strategies(
    signal: AISignalOut,
    active_strategies: list[str] | None = None,
) -> StrategyDecision:
    """
    Run all active strategies against a signal.
    Returns the decision from the first strategy that votes to trade,
    or ALERT_ONLY if all strategies decline.
    """
    strategies = active_strategies or DEFAULT_ACTIVE_STRATEGIES
    alert_reasons: list[str] = []

    for name in strategies:
        fn = STRATEGIES.get(name)
        if not fn:
            continue
        decision = fn(signal)
        if decision.should_trade:
            decision.reason = f"[{name}] {decision.reason}"
            return decision
        alert_reasons.append(f"{name}: {decision.reason}")

    return StrategyDecision(
        should_trade=False,
        action="ALERT_ONLY",
        reason="No strategy approved trade. " + " | ".join(alert_reasons),
    )
