"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_env: Literal["development", "staging", "production"] = "development"
    secret_key: str = "insecure-dev-secret-change-in-production"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://sentinel:sentinel@localhost:5432/market_sentinel"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- AI ---
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # --- Alpaca ---
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    # --- Safety (explicit opt-in required for live trading) ---
    paper_trading_only: bool = True
    real_trading_enabled: bool = False

    # --- Risk Limits ---
    max_daily_loss_usd: float = 50.0
    max_trade_size_usd: float = 25.0
    max_open_positions: int = 5
    min_confidence_to_trade: float = 80.0
    min_confidence_for_alert: float = 50.0
    allow_shorting: bool = False
    allow_options: bool = False

    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # --- Email ---
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_username: str = ""
    email_password: str = ""
    email_from: str = ""
    email_to: str = ""

    # --- News APIs ---
    newsapi_key: str = ""
    alphavantage_key: str = ""

    # --- Social APIs ---
    twitter_bearer_token: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    @field_validator("real_trading_enabled", mode="before")
    @classmethod
    def enforce_paper_trading_safety(cls, v: bool) -> bool:
        """Real trading requires explicit double opt-in."""
        paper_only = os.environ.get("PAPER_TRADING_ONLY", "true").lower()
        if paper_only == "true" and str(v).lower() == "true":
            raise ValueError(
                "Cannot enable REAL_TRADING_ENABLED when PAPER_TRADING_ONLY=true. "
                "Set PAPER_TRADING_ONLY=false first (understand the risks)."
            )
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_paper_mode(self) -> bool:
        return self.paper_trading_only or not self.real_trading_enabled

    @property
    def has_alpaca(self) -> bool:
        return bool(self.alpaca_api_key and self.alpaca_secret_key)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def has_email(self) -> bool:
        return bool(self.email_username and self.email_password and self.email_to)


@lru_cache
def get_settings() -> Settings:
    return Settings()
