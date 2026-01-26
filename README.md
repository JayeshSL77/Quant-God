# Inwezt AI

Inwezt AI is a comprehensive platform for financial analysis, leveraging advanced AI agents to process annual reports, concall transcripts, and market data. It provides quantitative models and AI-driven insights to help investors make informed decisions.

## 🚀 Key Features

- **AI-Driven Financial Analysis**: Extract insights from complex financial documents like annual reports and conference call transcripts.
- **Quantitative Models**: Integrated models for stock valuation and performance tracking.
- **Automated Data Scrapers**: Efficiently collect data from NSE and other financial sources.
- **Modern Web Interface**: A responsive and dynamic UI built with React and Vite.

## 🛠 Tech Stack

### Backend
- **Core**: Python 3.11+
- **Framework**: FastAPI, Uvicorn
- **AI/LLM**: LangChain, OpenAI, Google Gemini, Mistral AI, Anthropic
- **Data**: Pandas, NumPy, yfinance, nselib
- **Database**: SQLAlchemy, PostgreSQL (via psycopg2)
- **Cloud/Other**: Boto3 (AWS), python-dotenv

### Frontend
- **Framework**: Vite + React
- **Styling**: Vanilla CSS, TailwindCSS (for utility), Framer Motion (animations)
- **Icons**: Lucide React
- **Language**: TypeScript

## 📂 Project Structure

```text
inwezt_app/
├── backend/                # FastAPI application
│   ├── agents/             # AI agent logic and prompts
│   ├── api/                # API endpoints and main entry point
│   ├── database/           # DB schema and connection logic
│   ├── quant/              # Quantitative analysis models
│   └── utils/              # Shared utilities
├── inwezt_frontend/       # React + Vite frontend
│   ├── src/                # Frontend source code
│   └── public/             # Static assets
├── Dockerfile              # Containerization setup
├── requirements.txt        # Backend dependencies
└── run.py                  # Backend startup script
```

## 🚥 Getting Started

### Prerequisites
- Python 3.11+
- Node.js (for frontend)
- API Keys for AI services (OpenAI, Gemini, Mistral, etc.) configured in a `.env` file.

### Backend Setup
1. Navigate to the root folder:
   ```bash
   cd inwezt_app
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```
4. Run the backend:
   ```bash
   python run.py
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd inwezt_frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the dev server:
   ```bash
   npm run dev
   ```

## 🐳 Docker Support

Build and run the application using Docker:
```bash
docker build -t inwezt-app .
docker run -p 8000:8000 inwezt-app
```

## 📜 License

This project is licensed under the [ISC License](file:///Users/brainx/Desktop/Create/inwezt_app/inwezt_frontend/package.json).
