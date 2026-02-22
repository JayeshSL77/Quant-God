<p align="center">
  <h1 align="center">QUANT-GOD</h1>
  <p align="center"><strong>Autonomous AI-Native Hedge Fund Engine</strong></p>
  <p align="center">
    <em>11,000 Persistent Agents · Deep RAG · Institutional-Grade Equity Research at Infinite Scale</em>
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.109+-009688?logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/LangChain-0.1+-yellow?logo=chainlink&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-16+-4169E1?logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/License-ISC-green" />
</p>

---

## The Thesis

Traditional funds deploy ~50 analysts covering ~20 stocks each. That's a human bottleneck on alpha generation.

**Quant-God inverts the model.** We deploy a **dedicated, autonomous AI agent for every tradable asset** — over 11,000 tickers across Indian & global markets. Each agent maintains persistent state, ingests 15 years of filings (2010–2026), and synthesizes institutional-grade research memos in real-time.

This is not a chatbot. This is a **capital allocation engine**.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           QUANT-GOD ENGINE                               │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                    PORTFOLIO ORCHESTRATOR (V2)                      │  │
│  │                                                                    │  │
│  │  Natural Language Query                                            │  │
│  │       ↓                                                            │  │
│  │  Intent Detection → Query Decomposition → Ticker Extraction        │  │
│  │       ↓                                                            │  │
│  │  Agent Router (routes to 1..N ticker-specific agents)              │  │
│  │       ↓                                                            │  │
│  │  Multi-hop Reasoning · Comparison Engine · Thesis Synthesis        │  │
│  └───────┬──────────────────────────┬─────────────────────┬──────────┘  │
│          │                          │                     │              │
│  ════════╪══════════════════════════╪═════════════════════╪══════════    │
│  ║  11,000-AGENT SWARM — One Persistent Agent Per Ticker            ║   │
│  ║                                                                  ║   │
│  ║  ┌─────────────────┐  ┌─────────────────┐       ┌────────────┐  ║   │
│  ║  │ AGENT: RELIANCE  │  │ AGENT: TCS       │  ...  │ AGENT #N   │  ║   │
│  ║  │ ┌─────────────┐ │  │ ┌─────────────┐ │       │ ┌────────┐ │  ║   │
│  ║  │ │ MarketData  │ │  │ │ MarketData  │ │       │ │ Market │ │  ║   │
│  ║  │ │ RapidAPI    │ │  │ │ RapidAPI    │ │       │ │  Data  │ │  ║   │
│  ║  │ │ yfinance    │ │  │ │ yfinance    │ │       │ │        │ │  ║   │
│  ║  │ └─────────────┘ │  │ └─────────────┘ │       │ └────────┘ │  ║   │
│  ║  │ ┌─────────────┐ │  │ ┌─────────────┐ │       │ ┌────────┐ │  ║   │
│  ║  │ │ Filings     │ │  │ │ Filings     │ │       │ │Filings │ │  ║   │
│  ║  │ │ Concalls    │ │  │ │ Concalls    │ │       │ │Concall │ │  ║   │
│  ║  │ │ Ann. Reports│ │  │ │ Ann. Reports│ │       │ │Ann Rpt │ │  ║   │
│  ║  │ └─────────────┘ │  │ └─────────────┘ │       │ └────────┘ │  ║   │
│  ║  │ ┌─────────────┐ │  │ ┌─────────────┐ │       │ ┌────────┐ │  ║   │
│  ║  │ │ News Agent  │ │  │ │ News Agent  │ │       │ │  News  │ │  ║   │
│  ║  │ │ Sentiment   │ │  │ │ Sentiment   │ │       │ │Sentmnt │ │  ║   │
│  ║  │ └─────────────┘ │  │ └─────────────┘ │       │ └────────┘ │  ║   │
│  ║  │ ┌─────────────┐ │  │ ┌─────────────┐ │       │ ┌────────┐ │  ║   │
│  ║  │ │ Technical   │ │  │ │ Technical   │ │       │ │Techncl │ │  ║   │
│  ║  │ │ RSI/MACD    │ │  │ │ RSI/MACD    │ │       │ │RSI/EMA │ │  ║   │
│  ║  │ │ Bollinger   │ │  │ │ Bollinger   │ │       │ │Signals │ │  ║   │
│  ║  │ └─────────────┘ │  │ └─────────────┘ │       │ └────────┘ │  ║   │
│  ║  │                 │  │                 │       │            │  ║   │
│  ║  │ State: 15yr     │  │ State: 15yr     │       │ State:15yr │  ║   │
│  ║  │ filings cached  │  │ filings cached  │       │ cached     │  ║   │
│  ║  └─────────────────┘  └─────────────────┘       └────────────┘  ║   │
│  ║                                                                  ║   │
│  ║  NSE: ~2,000 tickers │ BSE: ~5,000 │ Global: ~4,000             ║   │
│  ╚══════════════════════════════════════════════════════════════════╝   │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                     INTELLIGENCE LAYER                              │  │
│  │                                                                    │  │
│  │  ┌──────────────┐  ┌───────────────┐  ┌─────────────────────────┐ │  │
│  │  │ Hybrid Search│  │    RAPTOR      │  │ Institutional Summarizer│ │  │
│  │  │ BM25 +       │  │  Recursive    │  │ Multi-doc synthesis     │ │  │
│  │  │ pgvector     │  │  Abstractive  │  │ across 300+ pg docs     │ │  │
│  │  │ Semantic     │  │  Processing   │  │                         │ │  │
│  │  └──────────────┘  └───────────────┘  └─────────────────────────┘ │  │
│  │                                                                    │  │
│  │  ┌──────────────┐  ┌───────────────┐  ┌─────────────────────────┐ │  │
│  │  │ Contrarian   │  │ Alert System  │  │ Index Builder           │ │  │
│  │  │ Finder       │  │ Real-time     │  │ Custom Indices          │ │  │
│  │  └──────────────┘  └───────────────┘  └─────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                      DATA PLATFORM                                 │  │
│  │                                                                    │  │
│  │  BSE/NSE Scrapers · 20+ Parallel Workers · 15-Year Depth          │  │
│  │  Smart Concurrency · Anti-Detection · Bulk Ingestion               │  │
│  │  Quant Analytics · Data Migration · Coverage Reporting             │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                      LLM BACKBONE                                  │  │
│  │                                                                    │  │
│  │  OpenAI GPT-4o · Google Gemini 2.0 Flash · Mistral Large           │  │
│  │  Hot-swappable · Retry w/ Exponential Backoff · Provider Fallback  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Core Capabilities

### 🧠 Multi-Agent Orchestration
The `OrchestratorV2` decomposes natural language queries into sub-questions, routes them to specialized agents in parallel via `ThreadPoolExecutor`, and synthesizes results through an institutional prompt template calibrated for portfolio managers.

### 📄 Deep RAG Pipeline
- **Hybrid Search**: BM25 lexical + pgvector semantic search with reciprocal rank fusion
- **RAPTOR**: Recursive Abstractive Processing for Tree-Organized Retrieval — hierarchical summarization of 300+ page documents
- **Chunking Engine**: Intelligent document segmentation with overlap-aware sliding windows (47KB engine)
- **15-Year Depth**: Every agent has access to filings from 2010–2026

### 📊 Quantitative Analytics
- Custom index construction
- Contrarian signal detection
- Metric extraction from unstructured filings
- Peer comparison with sector-relative valuation (discount/premium to sector PE)

### 🔍 Research Modes
| Mode | Behavior |
|------|----------|
| `deep_research` | Full 5-section institutional memo (Valuation → Earnings → Management → Risks → Thesis) |
| `business` | Qualitative-heavy analysis (omits valuation context) |
| `summary` | Thesis-only for quick screening |

### ⚡ Production Hardening
- **Rate Limiting** via SlowAPI
- **Error Tracking** via Sentry SDK
- **Metrics** via Prometheus FastAPI Instrumentator
- **Structured Logging** with JSON format in production
- **Request ID Middleware** for distributed tracing
- **Health Checks**: `/health` (liveness) + `/health/ready` (readiness with dependency verification)
- **CORS** with configurable origins
- **Streaming** via NDJSON Server-Sent Events for real-time research traces

---

## Repository Structure

```
.
├── api/                           # Core API Server
│   ├── agents/                    # AI Agent System
│   │   ├── orchestrator.py        # V2 institutional-grade orchestrator (1,300 LOC)
│   │   ├── agent_swarm.py         # 11,000-agent swarm coordinator
│   │   ├── market_data.py         # Price, fundamentals, peer data (RapidAPI)
│   │   ├── filings.py             # Concalls & annual report retrieval
│   │   ├── news.py                # Real-time news with sentiment
│   │   ├── technical.py           # RSI, MACD, Bollinger, moving averages
│   │   ├── thesis_generator.py    # Investment thesis synthesis
│   │   ├── contrarian_finder.py   # Contrarian signal detection
│   │   ├── index_builder.py       # Custom index construction
│   │   ├── metric_extractor.py    # Financial metric extraction from filings
│   │   ├── alert_system.py        # Real-time alert engine
│   │   ├── summarizer.py          # Multi-document summarization
│   │   └── router.py              # Semantic query routing
│   │
│   ├── database/                  # Data Layer
│   │   ├── database.py            # PostgreSQL connection & queries (38KB)
│   │   ├── hybrid_search.py       # BM25 + semantic hybrid search (30KB)
│   │   ├── chunking.py            # Document chunking engine (47KB)
│   │   ├── raptor.py              # RAPTOR hierarchical summarization
│   │   ├── embeddings.py          # Vector embedding generation
│   │   ├── semantic_search.py     # pgvector semantic search
│   │   ├── vector_setup.py        # Vector index provisioning
│   │   ├── institutional_summarizer.py  # Institutional-grade summarization
│   │   ├── news_sentinel.py       # News monitoring daemon
│   │   └── ingestion/             # Data ingestion pipeline
│   │
│   ├── endpoints/                 # API Layer
│   │   ├── main.py                # FastAPI app with production middleware
│   │   ├── agent.py               # Agent endpoint (streaming + sync)
│   │   ├── config.py              # Centralized configuration
│   │   ├── models.py              # Pydantic request/response models
│   │   ├── middleware.py          # RequestID, Logging, Error handling
│   │   ├── health.py              # Health check endpoints
│   │   ├── analytics.py           # Usage analytics
│   │   ├── advanced_analytics.py  # Advanced analytics endpoints
│   │   ├── personalization.py     # User preference learning
│   │   └── ab_test.py             # A/B testing framework
│   │
│   ├── core/                      # Shared Libraries
│   │   ├── charting/              # Visual RAG chart generation
│   │   ├── document/              # Document processing
│   │   └── utils/                 # Indian market utilities, tax calculator
│   │
│   ├── tests/                     # Test Suite
│   └── run.py                     # Application entry point
│
├── data_platform/                 # Data Acquisition Engine
│   ├── scrapers/                  # Scraper Fleet
│   │   ├── orchestrator.py        # Scraper orchestrator with smart concurrency
│   │   ├── bse_scraper.py         # BSE filing scraper (29KB)
│   │   ├── bse_orchestrator.py    # BSE-specific orchestration
│   │   ├── screener.py            # Screener.in data extraction
│   │   ├── bulk_ingest.py         # Bulk data ingestion
│   │   ├── run_parallel.sh        # 20+ parallel worker launcher
│   │   └── scrip_code_mapper.py   # BSE scrip code resolution
│   │
│   └── analytics/                 # Quantitative Analysis
│       ├── quant/                 # Quantitative models
│       │   ├── api_client.py      # Market data API client
│       │   ├── db_utils.py        # Database utilities
│       │   ├── data_migrator.py   # Schema migration
│       │   └── models.py          # Data models
│       └── core/                  # Core analytics engine
│
├── infrastructure/                # DevOps & Deployment
│   ├── docker/
│   │   └── Dockerfile             # Multi-stage production build
│   └── deployment/
│       ├── deploy.sh              # EC2 deployment automation
│       ├── setup_remote.sh        # Remote server provisioning
│       └── ...                    # Additional deployment scripts
│
├── docs/
│   └── ARCHITECTURE.md            # System architecture & data source hierarchy
│
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment template
└── LICENSE                        # ISC License
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 16+ with pgvector extension
- At least one LLM API key (OpenAI / Gemini / Mistral)

### Setup

```bash
# Clone
git clone https://github.com/JayeshSL77/Quant-God.git
cd Quant-God

# Virtual environment
python -m venv venv
source venv/bin/activate

# Dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys and database URL
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | One of three | GPT-4o for synthesis |
| `GEMINI_API_KEY` | One of three | Gemini 2.0 Flash |
| `MISTRAL_API_KEY` | One of three | Mistral Large |
| `LLM_PROVIDER` | Yes | `openai` \| `gemini` \| `mistral` |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `RAPIDAPI_KEY` | Yes | Indian Stock Exchange API |
| `SENTRY_DSN` | No | Error tracking |

### Run

```bash
# Development
python -m api.run

# Production
uvicorn api.endpoints.main:app --host 0.0.0.0 --port 8000 --workers 4

# Docker
docker build -f infrastructure/docker/Dockerfile -t quant-god .
docker run -p 8000:8000 --env-file .env quant-god
```

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/query` | POST | Synchronous query → full research memo |
| `/api/chat/stream` | POST | Streaming NDJSON with real-time agent traces |
| `/api/tax/calculate` | POST | Capital gains tax computation (Indian market) |
| `/api/market/status` | GET | NSE/BSE market hours status |
| `/api/feedback` | POST | Response quality feedback |
| `/health` | GET | Liveness check |
| `/health/ready` | GET | Readiness check with dependency verification |
| `/metrics` | GET | Prometheus metrics |
| `/docs` | GET | OpenAPI documentation |

### Example Query

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Should I invest in Reliance? Compare with TCS.",
    "analysis_mode": "deep_research"
  }'
```

---

## Data Pipeline

The scraper fleet enforces **15-year historical depth** across all assets:

```
Target Universe: 11,000+ tickers (NSE + BSE + Global)
Document Types:  Annual Reports, Concall Transcripts, Credit Ratings, Exchange Filings
Historical Span: 2010 – 2026
Workers:         20+ parallel (configurable via run_parallel.sh)
Anti-Detection:  Rotating user agents, adaptive rate limiting, exponential backoff
```

Ingested documents flow through:
1. **Chunking** → Overlap-aware sliding window segmentation
2. **Embedding** → Vector generation for semantic search
3. **RAPTOR** → Recursive hierarchical summarization
4. **BM25 Indexing** → tsvector for lexical retrieval
5. **Hybrid Search** → Reciprocal Rank Fusion at query time

---

## Deployment

### EC2 (Production)

```bash
# Package and deploy
python infrastructure/deployment/create_ec2_package.py
bash infrastructure/deployment/deploy.sh
```

### Docker

```bash
docker build -f infrastructure/docker/Dockerfile -t quant-god .
docker run -d -p 8000:8000 --env-file .env --name quant-god quant-god
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **API** | FastAPI, Uvicorn, Pydantic v2 |
| **AI/LLM** | LangChain, OpenAI, Google Gemini, Mistral |
| **Database** | PostgreSQL + pgvector, SQLAlchemy |
| **Search** | Hybrid BM25 + Semantic, RAPTOR |
| **Data** | yfinance, RapidAPI, BeautifulSoup, pdfplumber |
| **Infra** | Docker, AWS EC2, Boto3 |
| **Observability** | Sentry, Prometheus, structured JSON logging |
| **Resilience** | SlowAPI rate limiting, tenacity retries, exponential backoff |

---

## License

ISC License — see [LICENSE](LICENSE).

---

<p align="center">
  <strong>Engineered for Alpha. Defined by Scale.</strong>
</p>
