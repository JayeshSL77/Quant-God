# Inwezt - Architecture & Data Sources

> **CRITICAL**: This document defines the SINGLE SOURCE OF TRUTH for data in the application.

## Data Sources Hierarchy

| Data Type | PRIMARY Source | Fallback |
|-----------|---------------|----------|
| **Fundamentals** (PE, ROE, P/B, Net Margin) | `fetch_indian_data()` (RapidAPI) | yfinance |
| **Price/Quote** | `fetch_indian_data()` (RapidAPI) | yfinance |
| **Concalls/Transcripts** | Database (SQLite/AWS) | RapidAPI `/concalls` |
| **Annual Reports** | Database | RapidAPI `/annual_reports` |
| **News** | `NewsAgent` (yfinance API) | - |
| **Technical Indicators** | `TechnicalAgent` (calculated) | - |
| **Historical Prices** | Database → RapidAPI | yfinance |

---

## Backend Architecture

```
backend/
├── agents/                    # AI Agent System
│   ├── orchestrator.py       # Main router - DO NOT add data fetching here
│   ├── market_data.py        # Uses fetch_indian_data()
│   ├── filings.py            # Uses database concalls/reports
│   ├── news.py               # Uses yfinance news API
│   └── technical.py          # Calculates indicators
│
├── core/utils/
│   └── fetch_indian_data.py  # ⭐ PRIMARY data source (RapidAPI)
│
├── database/
│   └── database.py           # SQLite/AWS for cached data
│
└── api/
    └── agent.py              # FastAPI endpoints
```

---

## Agent Responsibilities

| Agent | Purpose | Data Source |
|-------|---------|-------------|
| `OrchestratorV2` | Routes queries, coordinates agents | None (router only) |
| `MarketDataAgent` | Price, fundamentals, peer data | `fetch_indian_data()` |
| `FilingsAgent` | Concalls, annual reports | Database |
| `NewsAgent` | Recent news | yfinance API |
| `TechnicalAgent` | RSI, MACD, moving averages | Calculated from price data |

---

## Query Flow

```
User Query
    ↓
OrchestratorV2.process_v2()
    ↓
┌──────────────────────────────────────┐
│ Intent Detection                      │
│ - Single Stock → _process_single()   │
│ - Comparison → _process_comparison() │
└──────────────────────────────────────┘
    ↓
Parallel Agent Execution
    ↓
LLM Synthesis
    ↓
Response + Chart/Table
```

---

## Frontend Architecture

```
inwezt_frontend/src/
├── App.tsx                   # Main chat interface
├── components/
│   ├── ChatMessage.tsx       # Message display (Markdown, table, chart)
│   ├── ComparisonTable.tsx   # Side-by-side stock comparison
│   ├── ResearchTrace.tsx     # Agent status circles
│   └── ThinkingStatus.tsx    # Loading indicator
├── hooks/
│   └── useChat.ts            # WebSocket/SSE chat logic
├── styles/
│   └── App.css               # All styles
└── types.ts                  # TypeScript interfaces
```

---

## Rules for Developers

1. **NEVER** fetch fundamentals (PE, ROE, etc.) directly - always use `fetch_indian_data()`
2. **NEVER** add data fetching logic in orchestrator - delegate to agents
3. **ALWAYS** check `comparison_mode` flag in agents for lightweight processing
4. **ALWAYS** use cached summaries from database before calling LLM summarization
