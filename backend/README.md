# Pesa Analyser Backend

FastAPI backend for statement uploads, analysis, payments, and reporting.

## Features

- PDF, CSV, and Excel statement parsing
- AI-powered transaction analysis
- M-PESA STK Push payments
- PDF and CSV reports
- Redis caching and Celery background jobs
- PostgreSQL and Docker support

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
# Generate and set this key before accepting password-protected PDFs:
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
alembic upgrade head

# Terminal 1: API
uvicorn app.main:app --reload

# Terminal 2: background jobs
celery -A app.tasks:celery_app worker --loglevel=info --concurrency=2
```

## Large uploads and background analysis

Uploads are copied to `UPLOAD_DIR` in 1 MiB chunks, validated without reading
the whole file into memory, and queued for analysis. PDF pages are extracted in
sequence and update the analysis progress field while parsing. The API returns
`202 Accepted`; clients should use the existing analysis status endpoint or
WebSocket until the status is `completed` or `failed`.

The API and every Celery worker must use the same persistent `UPLOAD_DIR`.
For Kubernetes this means a shared read/write-many volume (the included worker
deployment mounts `uploads-pvc`). Configure `MAX_FILE_SIZE` consistently with
the reverse-proxy request-body limit. Worker concurrency is intentionally
bounded; increase it only after measuring memory use for representative large
statements. Jobs use late acknowledgements and are redelivered if a worker is
lost.

Password-protected PDF passwords are encrypted before being placed on the
Celery broker. Set the same generated `UPLOAD_PASSWORD_ENCRYPTION_KEY` for the
API and worker; do not commit it to source control.
