# Analyez API

The core backend service for the Analyez platform, built with FastAPI.

## Key Features
- **AI Agents**: Orchestrator, Market, and Technical analysis agents.
- **Streaming Response**: Real-time chat streaming.
- **Waitlist Integration**: Manages waitlist signups and positioning.
- **Database**: PostgreSQL integration via SQLAlchemy.

## Setup

1. **Environment**: Ensure `.env` is present at project root.
2. **Install**:
   ```bash
   pip install -r requirements.lock
   ```
3. **Run**:
   ```bash
   python run.py
   ```
   Server runs on `http://localhost:8000`.

## Structure
- `endpoints/`: API route handlers
- `agents/`: AI logic and prompts
- `core/`: Configuration and shared utilities
- `database/`: Database models and connection logic
