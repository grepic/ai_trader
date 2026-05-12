"""Reporting service: Telegram, Email, and daily/morning reports."""

from __future__ import annotations

import logging
import smtplib
from datetime import date, datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class ReportingService:
    """Handles sending reports via Telegram and Email."""

    def __init__(self) -> None:
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Telegram
    # ------------------------------------------------------------------

    async def send_telegram(self, message: str) -> bool:
        """Send a message via Telegram Bot API."""
        settings = self._settings
        if not settings.has_telegram:
            logger.debug("Telegram not configured — skipping")
            return False

        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": settings.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                logger.info("Telegram message sent")
                return True
        except Exception as e:
            logger.error("Telegram send failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Email
    # ------------------------------------------------------------------

    async def send_email(self, subject: str, body_html: str) -> bool:
        """Send an HTML email via SMTP."""
        settings = self._settings
        if not settings.has_email:
            logger.debug("Email not configured — skipping")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.email_from or settings.email_username
            msg["To"] = settings.email_to

            msg.attach(MIMEText(body_html, "html"))

            with smtplib.SMTP(settings.email_smtp_host, settings.email_smtp_port) as server:
                server.starttls()
                server.login(settings.email_username, settings.email_password)
                server.sendmail(
                    settings.email_username,
                    settings.email_to,
                    msg.as_string(),
                )
            logger.info("Email sent: %s", subject)
            return True
        except Exception as e:
            logger.error("Email send failed: %s", e)
            return False

    # ------------------------------------------------------------------
    # Report formatters
    # ------------------------------------------------------------------

    def format_daily_report_telegram(self, report_data: dict[str, Any]) -> str:
        mode = "📄 PAPER" if report_data.get("paper_mode") else "💰 LIVE"
        daily_pl = report_data.get("daily_pl", 0)
        pl_emoji = "📈" if daily_pl >= 0 else "📉"

        lines = [
            f"<b>🤖 Market Sentinel AI — Daily Report {mode}</b>",
            f"📅 {report_data.get('report_date', date.today().isoformat())}",
            "",
            f"<b>Portfolio</b>",
            f"  Account Value: ${report_data.get('account_value', 0):,.2f}",
            f"  Cash: ${report_data.get('cash_balance', 0):,.2f}",
            f"  {pl_emoji} Daily P/L: ${daily_pl:+,.2f}",
            f"  Realized P/L: ${report_data.get('realized_pl', 0):+,.2f}",
            f"  Unrealized P/L: ${report_data.get('unrealized_pl', 0):+,.2f}",
            "",
            f"<b>Trading Activity</b>",
            f"  Trades: {report_data.get('total_trades', 0)} (W:{report_data.get('winning_trades', 0)} L:{report_data.get('losing_trades', 0)})",
            f"  Signals: {report_data.get('signals_generated', 0)} generated, "
            f"{report_data.get('signals_traded', 0)} traded, "
            f"{report_data.get('signals_ignored', 0)} ignored",
        ]

        best = report_data.get("best_trade_ticker")
        if best:
            lines.append(f"  🏆 Best: {best} ${report_data.get('best_trade_pl', 0):+,.2f}")

        worst = report_data.get("worst_trade_ticker")
        if worst:
            lines.append(f"  💀 Worst: {worst} ${report_data.get('worst_trade_pl', 0):+,.2f}")

        lines += [
            "",
            f"  Risk Events: {report_data.get('risk_events_count', 0)}",
            "",
            "<i>⚠️ For research/educational purposes only. Not financial advice.</i>",
        ]
        return "\n".join(lines)

    def format_trade_alert_telegram(
        self,
        action: str,
        ticker: str,
        quantity: float,
        price: float,
        confidence: float,
        reasoning: str,
        paper_mode: bool = True,
    ) -> str:
        mode = "PAPER" if paper_mode else "🔴 LIVE"
        emoji = "🟢 BUY" if action == "BUY" else "🔴 SELL" if action == "SELL" else action
        return (
            f"<b>[{mode}] Trade Executed — {emoji}</b>\n"
            f"Ticker: <b>{ticker}</b>\n"
            f"Quantity: {quantity:.4f} shares\n"
            f"Price: ${price:.2f}\n"
            f"Total: ${quantity * price:.2f}\n"
            f"Confidence: {confidence:.0f}%\n"
            f"Reason: {reasoning[:200]}\n"
            f"\n<i>⚠️ Paper trading only.</i>"
        )

    def format_risk_alert_telegram(
        self, event_type: str, description: str, severity: str
    ) -> str:
        emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(severity, "⚠️")
        return (
            f"<b>{emoji} Risk Alert: {event_type}</b>\n"
            f"Severity: {severity.upper()}\n"
            f"Details: {description}"
        )

    def format_morning_report_telegram(
        self,
        account_value: float,
        open_positions: int,
        watchlist_count: int,
        market_open: bool,
        paper_mode: bool = True,
    ) -> str:
        mode = "📄 PAPER" if paper_mode else "💰 LIVE"
        market_status = "🟢 OPEN" if market_open else "🔴 CLOSED"
        return (
            f"<b>🌅 Market Sentinel AI — Morning Report {mode}</b>\n"
            f"🕰 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"Market: {market_status}\n"
            f"Account Value: ${account_value:,.2f}\n"
            f"Open Positions: {open_positions}\n"
            f"Watching: {watchlist_count} tickers\n\n"
            f"<i>Bot is active and monitoring markets.</i>"
        )

    def format_email_daily_report(self, report_data: dict[str, Any]) -> str:
        mode = "PAPER TRADING" if report_data.get("paper_mode") else "LIVE TRADING"
        daily_pl = report_data.get("daily_pl", 0)
        pl_color = "#27ae60" if daily_pl >= 0 else "#e74c3c"

        return f"""
        <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2c3e50;">🤖 Market Sentinel AI — Daily Report</h2>
        <p style="color: #7f8c8d;">{mode} | {report_data.get('report_date', '')}</p>

        <table style="width:100%; border-collapse: collapse; margin: 20px 0;">
          <tr style="background: #ecf0f1;">
            <th style="padding: 10px; text-align: left;">Metric</th>
            <th style="padding: 10px; text-align: right;">Value</th>
          </tr>
          <tr><td style="padding: 8px;">Account Value</td>
              <td style="padding: 8px; text-align: right;">${report_data.get('account_value', 0):,.2f}</td></tr>
          <tr><td style="padding: 8px;">Cash Balance</td>
              <td style="padding: 8px; text-align: right;">${report_data.get('cash_balance', 0):,.2f}</td></tr>
          <tr><td style="padding: 8px;">Daily P/L</td>
              <td style="padding: 8px; text-align: right; color: {pl_color};">${daily_pl:+,.2f}</td></tr>
          <tr><td style="padding: 8px;">Total Trades</td>
              <td style="padding: 8px; text-align: right;">{report_data.get('total_trades', 0)}</td></tr>
          <tr><td style="padding: 8px;">Win Rate</td>
              <td style="padding: 8px; text-align: right;">
                {(report_data.get('winning_trades', 0) / max(1, report_data.get('total_trades', 1)) * 100):.0f}%
              </td></tr>
          <tr><td style="padding: 8px;">Signals Generated</td>
              <td style="padding: 8px; text-align: right;">{report_data.get('signals_generated', 0)}</td></tr>
          <tr><td style="padding: 8px;">Risk Events</td>
              <td style="padding: 8px; text-align: right;">{report_data.get('risk_events_count', 0)}</td></tr>
        </table>

        <p style="color: #e74c3c; font-size: 12px;">
          ⚠️ This software is for research and educational purposes only.
          It is not financial advice. Paper trading is enabled by default.
          Real trading involves risk of loss.
        </p>
        </body></html>
        """
