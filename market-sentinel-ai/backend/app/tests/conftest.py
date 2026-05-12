"""pytest configuration — async fixtures and test settings."""

import os
import pytest

# Use in-memory SQLite for tests to avoid requiring PostgreSQL
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("PAPER_TRADING_ONLY", "true")
os.environ.setdefault("REAL_TRADING_ENABLED", "false")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

# Make pytest-asyncio work globally
pytest_plugins = ["pytest_asyncio"]
