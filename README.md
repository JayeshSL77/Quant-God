# Inwezt AI

<div align="center">
  <h3>AI Powered Investing Co-Pilot for Mass-Affluent Indian Investors</h3>
  <p>Quantitative models and AI-driven insights to help investors make informed decisions.</p>
</div>

---

## 🚀 Overview

Inwezt AI is a comprehensive platform leveraging advanced AI agents to process annual reports, concall transcripts, and market data. It combines deep financial analysis with an intuitive chat interface to democratize institutional-grade investment research.

## 🛠 Tech Stack

### Backend
- **Core**: Python 3.11+, FastAPI
- **AI/LLM**: LangChain, OpenAI, Google Gemini, Mistral AI
- **Data Processing**: Pandas, NumPy, yfinance, nselib
- **Database**: PostgreSQL (SQLAlchemy)

### Frontend
- **Framework**: React + Vite + TypeScript
- **Styling**: Vanilla CSS (Premium Design System)
- **State/Effects**: Framer Motion

## 📂 Project Structure

```text
inwezt_app/
├── backend/                # FastAPI application & AI Agents
│   ├── agents/             # Agent logic (Market, Filings, Technicals)
│   ├── api/                # API Endpoints
│   └── database/           # DB Models & Connections
├── inwezt_frontend/       # React Frontend
│   ├── src/                # Components & Styles
│   └── public/             # Static Assets
├── Dockerfile              # Container Configuration
└── requirements.txt        # Backend Dependencies
```

## 🚥 Local Development

### Prerequisites
- Python 3.11+
- Node.js v18+
- PostgreSQL (optional, can run with SQLite for dev)

### 1. Backend Setup
```bash
cd inwezt_app
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Setup Environment
cp .env.example .env
# Edit .env with your API keys (OPENAI_API_KEY, etc.)

# Run Development Server
python run.py
```

### 2. Frontend Setup
```bash
cd inwezt_frontend
npm install
npm run dev
```

## 🚀 Production Deployment

### Option A: Docker (Recommended)
Build and run the entire stack containerized.
```bash
docker build -t inwezt-app .
docker run -d -p 8000:8000 --env-file .env inwezt-app
```

### Option B: Manual Deployment

**Frontend Build**
```bash
cd inwezt_frontend
npm run build
# Serve the 'dist' folder using Nginx, Vercel, or Netlify
```

**Backend Service**
Run using a production-grade ASGI server like Gunicorn.
```bash
cd inwezt_app
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend.api.main:app
```

## 📜 License
This project is licensed under the ISC License.
