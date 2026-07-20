# AlphaSight — AI Stock Trading Agent

An autonomous AI trading agent that monitors markets 24/7, combining real-time technical analysis, news sentiment, fundamental scans, and a unified scoring model to identify high-probability trades.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AlphaSight MVP                           │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (Next.js + React + Tailwind)                          │
│  Port 3000 — proxies /api/* → backend:8000                      │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────────┐  │
│  │Dashboard │Portfolio │Watchlist │ Reports  │  Settings    │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  Backend (FastAPI + Python)                                     │
│  Port 8000 — REST API at /api/v1/*                               │
│  ┌─────────┬─────────┬──────────┬────────┬─────────┬─────────┐  │
│  │Scanner  │Sentiment│Technicals│ Risk   │ Scoring │Decisions│  │
│  ├─────────┼─────────┼──────────┼────────┼─────────┼─────────┤  │
│  │Portfolio│Notify   │ Reports  │ Config │ Schemas │  Redis  │  │
│  └─────────┴─────────┴──────────┴────────┴─────────┴─────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL — stocks, trades, portfolio, signals, reports       │
│  Redis — market data cache, real-time pub/sub, session state    │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- API keys for Polygon.io, Alpaca, and OpenAI

### Setup

1. **Clone and configure environment**
   ```bash
   git clone <repo-url> alphsight
   cd alphsight
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. **Start the stack**
   ```bash
   docker-compose up -d
   ```

3. **Access the dashboard**
   - Frontend: http://localhost:3000
   - Backend API docs: http://localhost:8000/docs
   - Health check: http://localhost:8000/api/v1/health

### Development (without Docker)

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Backend Modules

| Module          | Path                          | Purpose                                    |
|-----------------|-------------------------------|--------------------------------------------|
| `scanner`       | `app/engines/scanner.py`      | Market-wide opportunity scanning           |
| `sentiment`     | `app/engines/sentiment.py`    | News & social media sentiment analysis     |
| `technicals`    | `app/engines/technicals.py`   | Technical indicators & chart patterns      |
| `risk`          | `app/engines/risk.py`         | Position sizing, stop-loss, risk controls  |
| `scoring`       | `app/engines/scoring.py`      | Unified multi-factor scoring model         |
| `decisions`     | `app/engines/decisions.py`    | Trade execution decisions                  |
| `portfolio`     | `app/engines/portfolio.py`    | Portfolio tracking & performance           |
| `notifications` | `app/engines/notifications.py`| Alerts, Discord/Slack/email notifications  |
| `reports`       | `app/engines/reports.py`      | Daily/weekly performance reports           |

## API Endpoints

All routes are prefixed with `/api/v1/`.

| Method | Path                  | Description          |
|--------|-----------------------|----------------------|
| GET    | `/api/v1/health`      | Health check         |
| GET    | `/api/v1/stocks`      | List tracked stocks  |
| GET    | `/api/v1/signals`     | Active trade signals |
| GET    | `/api/v1/portfolio`   | Portfolio snapshot   |
| GET    | `/api/v1/trades`      | Trade history        |
| GET    | `/api/v1/watchlist`   | Watchlist items      |
| GET    | `/api/v1/reports`     | Performance reports  |

## Environment Variables

See `.env.example` for the full list. Key variables:

- `POLYGON_API_KEY` — Market data provider
- `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` — Trading execution
- `OPENAI_API_KEY` — LLM for sentiment & analysis
- `DATABASE_URL` — PostgreSQL connection
- `REDIS_URL` — Redis connection
- `DISCORD_WEBHOOK` — Optional notification channel
