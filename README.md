# Inwezt AI

<div align="center">
  <h3>AI-Powered Investing Co-Pilot for Indian Investors</h3>
  <p>Institutional-grade stock analysis with AI agents for market data, filings, and technical insights.</p>
</div>

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js v18+
- API Keys: RapidAPI (Indian Stock API), Mistral AI

---

## 📦 Installation

### 1. Clone & Setup Environment

```bash
git clone https://github.com/your-username/inwezt_app.git
cd inwezt_app

# Copy environment template
cp .env.example .env
```

### 2. Configure API Keys

Edit `.env` and add your keys:
```env
RAPIDAPI_KEY=your-rapidapi-key-here
MISTRAL_API_KEY=your-mistral-api-key-here
```

> 💡 Get RapidAPI key from: https://rapidapi.com/suneetk92/api/indian-stock-exchange-api2

---

## 🖥️ Running the Application

### Terminal 1: Start Backend

```bash
cd inwezt_app/backend

# Create virtual environment (first time only)
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR: venv\Scripts\activate  # Windows

# Install dependencies (first time only)
pip install -r requirements.txt

# Start the backend server
python -m uvicorn api.agent:app --reload --port 8000
```

✅ Backend running at: `http://localhost:8000`

---

### Terminal 2: Start Frontend

```bash
cd inwezt_app/inwezt_frontend

# Install dependencies (first time only)
npm install

# Start the frontend dev server
npm run dev
```

✅ Frontend running at: `http://localhost:3000`

---

## 💬 Getting Responses

1. Open `http://localhost:3000` in your browser
2. Type a query in the chat input:
   - **Single Stock**: `"Analyze Reliance Industries"`
   - **Comparison**: `"Compare TCS vs Infosys"`
   - **Specific Question**: `"What is HDFC Bank's ROE?"`
3. Watch the AI research agents process your query
4. Get institutional-grade analysis with charts and tables

---

## 📂 Project Structure

```
inwezt_app/
├── backend/                 # FastAPI + AI Agents
│   ├── agents/              # Orchestrator, Market, Filings, Technical agents
│   ├── api/                 # REST API endpoints
│   ├── core/                # Data sources & utilities
│   └── database/            # SQLite/PostgreSQL models
├── inwezt_frontend/         # React + Vite + TypeScript
│   ├── src/components/      # Chat UI, Comparison Tables
│   └── src/styles/          # Premium dark theme
├── .env.example             # Environment template
└── ARCHITECTURE.md          # Data source documentation
```

---

## 🔧 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat/stream` | POST | Stream AI responses |
| `/api/health` | GET | Health check |

---

## 🛠 Tech Stack

- **Backend**: Python, FastAPI, Mistral AI, LangChain
- **Frontend**: React, Vite, TypeScript, Framer Motion
- **Data**: RapidAPI Indian Stock API, yfinance (fallback)

---

## 📜 License

ISC License
