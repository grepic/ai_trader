"""pytest configuration — async fixtures and test settings."""

import os

# Use in-memory SQLite for tests (no PostgreSQL required)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["PAPER_TRADING_ONLY"] = "true"
os.environ["REAL_TRADING_ENABLED"] = "false"
os.environ["OPENAI_API_KEY"] = "test-key-not-real"
os.environ["ALPACA_API_KEY"] = ""
os.environ["ALPACA_SECRET_KEY"] = ""
