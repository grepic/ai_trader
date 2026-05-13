# Market Sentinel AI

An automated AI-powered stock trading assistant.

> **⚠️ DISCLAIMER:** This software is for research and educational purposes only.
> It is **not** financial advice. Paper trading is enabled by default.
> Real trading involves risk of loss. Never trade real money you cannot afford to lose.

---

## Features

| Module | Description |
|--------|-------------|
| **Data Ingestion** | Pluggable sources: NewsAPI, SEC EDGAR, Reddit, mock news |
| **Source Verification** | Credibility scoring, corroboration detection, deduplication |
| **AI Analysis** | OpenAI-compatible LLM produces structured JSON signals |
| **Risk Engine** | Deterministic safety gate — daily loss, position limits, emergency stop |
| **Paper Trading** | Alpaca paper trading integration with mock fallback |
| **Reporting** | Telegram + Email alerts, daily/morning reports |
| **Dashboard** | React + TypeScript dashboard with real-time updates |
| **Backtesting** | Replay historical signals with performance metrics |

---

## Quick Start (Docker)

### 1. Clone and configure

```bash
git clone <repo-url>
cd market-sentinel-ai

# Create your environment file
cp .env.example .env
# Edit .env and add your API keys (see Configuration section)
```

### 2. Start all services

```bash
docker compose up -d
```

Services:
- **Backend API**: http://localhost:8000
- **Frontend Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### 3. Check health

```bash
curl http://localhost:8000/health
# {"status": "ok", "timestamp": "..."}
```

---

## Local Development (without Docker)

### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis (via Docker for convenience)
docker compose up -d db redis

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://sentinel:sentinel@localhost:5432/market_sentinel"
export REDIS_URL="redis://localhost:6379/0"
export PAPER_TRADING_ONLY="true"
export REAL_TRADING_ENABLED="false"

# Run the API
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server (proxies /api to localhost:8000)
npm run dev
# Dashboard: http://localhost:3000
```

### Run Tests

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run all tests (unit + API integration + pipeline integration)
pytest

# Run with coverage report
pytest --cov=app --cov-report=term-missing

# Run specific suites
pytest app/tests/test_risk_engine.py -v      # Risk engine unit tests
pytest app/tests/test_strategies.py -v      # Strategy unit tests
pytest app/tests/test_api.py -v             # API endpoint integration tests
pytest app/tests/test_pipeline.py -v        # Full trading pipeline tests
pytest app/tests/test_backtesting.py -v     # Backtesting engine tests
pytest app/tests/test_verification.py -v    # Source verification tests
pytest app/tests/test_mock_broker.py -v     # Mock broker tests
```

---

## Configuration

All configuration is via environment variables (`.env` file). Key settings:

### Safety (DO NOT change defaults without understanding the risks)

```env
PAPER_TRADING_ONLY=true          # Master safety switch
REAL_TRADING_ENABLED=false       # Must be explicitly enabled
```

> Both flags must be changed simultaneously to enable real trading. This is
> an intentional double opt-in safety mechanism.

### Risk Limits

```env
MAX_DAILY_LOSS_USD=50            # Stop trading if daily loss exceeds this
MAX_TRADE_SIZE_USD=25            # Max spend per single trade
MAX_OPEN_POSITIONS=5             # Max concurrent positions
MIN_CONFIDENCE_TO_TRADE=80       # AI confidence threshold to execute
MIN_CONFIDENCE_FOR_ALERT=50      # Alert threshold (no trade)
ALLOW_SHORTING=false             # Shorting disabled by default
ALLOW_OPTIONS=false              # Options disabled by default
```

### Broker (Alpaca)

```env
ALPACA_API_KEY=your-paper-key
ALPACA_SECRET_KEY=your-paper-secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets   # Paper endpoint (safe default)
```

Get free paper trading API keys at: https://alpaca.markets

### AI

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini        # Cost-efficient default
```

Any OpenAI-compatible API works (set `OPENAI_BASE_URL` for alternatives).

### Notifications

```env
TELEGRAM_BOT_TOKEN=...          # Create via @BotFather
TELEGRAM_CHAT_ID=...            # Your chat or group ID

EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_USERNAME=your@email.com
EMAIL_PASSWORD=your-app-password
EMAIL_TO=alerts@email.com
```

The app works without notifications configured — they're optional.

---

## Architecture

```
market-sentinel-ai/
├── backend/
│   └── app/
│       ├── main.py              # FastAPI app + lifespan
│       ├── config.py            # Settings (pydantic-settings)
│       ├── database.py          # Async SQLAlchemy
│       ├── models/              # ORM models
│       ├── schemas/             # Pydantic response schemas
│       ├── api/routers/         # FastAPI route handlers
│       ├── services/
│       │   ├── data_ingestion/  # News/SEC/social collectors
│       │   ├── verification/    # Credibility scoring
│       │   ├── ai_analysis/     # LLM signal generation
│       │   ├── strategy/        # Trade pipeline orchestration
│       │   ├── risk/            # Risk management engine
│       │   ├── broker/          # Broker abstraction layer
│       │   ├── reporting/       # Telegram/Email reports
│       │   └── backtesting/     # Historical simulation
│       ├── jobs/                # APScheduler background jobs
│       └── tests/               # pytest test suite
├── frontend/
│   └── src/
│       ├── pages/               # Dashboard pages
│       ├── components/          # Reusable UI components
│       ├── api/                 # API client
│       ├── hooks/               # React hooks
│       └── types/               # TypeScript types
├── docker-compose.yml
├── .env.example
└── README.md
```

### Pipeline Flow

```
Data Sources → SourceItem (DB)
    ↓
Verification Engine → VerifiedEvent (DB)
    ↓  [if TRADE_ALLOWED or ALERT_ONLY]
AI Analysis Engine → AISignal (DB)
    ↓  [if trade decision is BUY/SELL]
Risk Engine → TradeDecision (DB)
    ↓  [if all checks pass]
Broker Client → Order (DB)
    ↓
Reporting → Telegram / Email / Dashboard
```

---

## API Reference

Full interactive docs available at: http://localhost:8000/docs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/overview` | Dashboard summary |
| GET | `/api/signals` | Latest AI signals |
| GET | `/api/signals/{id}` | Single signal detail |
| GET | `/api/trades` | Trade decisions |
| GET | `/api/positions` | Current positions |
| GET | `/api/positions/portfolio` | Portfolio snapshot |
| GET | `/api/sources` | Raw collected items |
| GET | `/api/sources/verified` | Verified events |
| GET | `/api/risk/status` | Risk status |
| POST | `/api/bot/pause` | Pause the bot |
| POST | `/api/bot/resume` | Resume the bot |
| POST | `/api/bot/emergency-stop` | Emergency stop + close all |
| GET | `/api/watchlist` | List watchlist |
| POST | `/api/watchlist` | Add ticker |
| DELETE | `/api/watchlist/{ticker}` | Remove ticker |
| GET | `/api/reports/daily` | Daily reports |
| GET | `/api/reports/daily/{date}` | Report for specific date |
| GET | `/api/logs` | System audit log (filters: level, ticker, component) |
| POST | `/api/positions/{ticker}/close` | Close a specific open position |
| POST | `/api/backtest/run` | Run backtest |
| WS  | `/ws` | Real-time event stream |

---

## Dashboard Pages

| Page | Path | Description |
|------|------|-------------|
| Overview | `/` | Bot status, P/L, risk meter, live equity curve, recent signals |
| Signals | `/signals` | AI-generated trading signals with reasoning |
| Trades | `/trades` | Trade decisions + execution status |
| Positions | `/positions` | Open positions with live P/L |
| Sources | `/sources` | Raw data and verification scores |
| Risk Controls | `/risk` | Pause/resume/emergency stop |
| Backtest | `/backtest` | Historical strategy simulation |
| Reports | `/reports` | Daily P&L summaries with win rate and trade stats |
| Logs | `/logs` | Filterable system audit log (level, ticker, component) |
| Settings | `/settings` | Watchlist and API key management |

### Real-time WebSocket

The dashboard connects to `ws://localhost:3000/ws` and receives live events:

```json
{ "type": "signal",    "data": { "ticker": "AAPL", "trade_decision": "BUY", ... }, "ts": "..." }
{ "type": "trade",     "data": { "ticker": "AAPL", "side": "buy", "quantity": 2, ... }, "ts": "..." }
{ "type": "portfolio", "data": { "account_value": 10250.0, ... }, "ts": "..." }
{ "type": "risk",      "data": { "event_type": "daily_loss_warning", "severity": "warning", ... }, "ts": "..." }
{ "type": "heartbeat", "data": { "connections": 1 }, "ts": "..." }
```

The Overview page shows a live equity curve that builds up from portfolio events in real time. The connection auto-reconnects with exponential backoff on disconnect.

---

## Trading Decision Pipeline

Every trade must pass ALL of these checks:

1. Bot is not emergency-stopped or manually paused
2. Real trading guard (paper mode by default)
3. Market is open
4. Ticker is in the active watchlist
5. AI confidence ≥ `MIN_CONFIDENCE_TO_TRADE` (default: 80%)
6. Risk level is not "extreme"
7. Daily loss limit not exceeded
8. Open positions below maximum
9. Ticker not in cooldown period
10. Ticker trade count ≤ 3 per day
11. Sufficient cash (max trade size check)
12. Price ≥ $1.00 (penny stock filter)

If ANY check fails, the trade is blocked and the reason is logged.

---

## Background Jobs

| Job | Frequency | Description |
|-----|-----------|-------------|
| `ingest_data` | Every 2 min | Collect from all data sources |
| `process_signals` | Every 1 min | Verify → AI → Risk → Trade |
| `portfolio_snapshot` | Every 5 min | Save portfolio state + WS broadcast |
| `risk_monitor` | Every 10 min | Alert at 70%/100% of daily loss limit |
| `morning_report` | 9:00 AM ET | Pre-market briefing |
| `daily_report` | 4:30 PM ET | End-of-day summary |

---

## Adding New Data Sources

Implement `BaseSource` in `backend/app/services/data_ingestion/sources.py`:

```python
class MyCustomSource(BaseSource):
    source_name = "my_source"
    source_type = "news"  # news|sec|social|earnings|price

    async def fetch(self, tickers: list[str]) -> list[dict]:
        # Return list of raw item dicts
        return [{
            "source_name": self.source_name,
            "source_type": self.source_type,
            "source_url": "https://...",
            "ticker_detected": "AAPL",
            "headline": "...",
            "content": "...",
            "published_at": datetime.now(timezone.utc),
        }]
```

Then add it to `get_all_sources()` in the same file.

---

## Enabling Real Trading (Use With Extreme Caution)

Real trading is disabled by default with two independent safety flags. To enable:

1. Set `PAPER_TRADING_ONLY=false` in your `.env`
2. Set `REAL_TRADING_ENABLED=true` in your `.env`
3. Configure real Alpaca API keys (not paper keys)
4. Change `ALPACA_BASE_URL=https://api.alpaca.markets` (live endpoint)
5. Start with very small `MAX_TRADE_SIZE_USD` (e.g., $1-5)
6. Monitor closely

**The author assumes no responsibility for financial losses from live trading.**

---

## License

MIT License — see LICENSE file.

This project is for educational and research purposes. Not financial advice.
