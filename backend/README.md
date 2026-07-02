# Pesa Analyser Backend

FastAPI-based backend for Pesa Analyser with AI-powered financial analysis.

## Features
- PDF/CVS/Excel parsing with password support
- AI-powered transaction analysis (Gemini/Claude)
- M-PESA STK Push payment integration
- PDF and CSV report generation
- Email report delivery
- Redis caching
- PostgreSQL database
- Docker support

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env .env.local

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
