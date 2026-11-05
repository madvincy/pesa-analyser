# Pesa Statement Analyser

[![Deploy to Azure](https://img.shields.io/badge/Deploy%20to-Azure-blue)](https://portal.azure.com)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=flat&logo=kubernetes&logoColor=white)](https://kubernetes.io)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## 🌟 Overview

Pesa Analyser is an AI-powered financial analysis platform that helps users understand their spending patterns, income trends, and overall financial health by analyzing M-PESA and bank statements. Built with modern technologies and enterprise-grade architecture.

### Key Features

- 🤖 **AI-Powered Analysis**: 20+ financial insights using Gemini/Claude AI
- 📊 **Interactive Dashboard**: Beautiful charts and visualizations with dark/light theme
- 💳 **M-PESA Integration**: Seamless payment processing via STK Push
- 📱 **Responsive Design**: Works on all devices with Shadcn UI
- 🔒 **Enterprise Security**: AES-256 encryption, data anonymization
- 📧 **Email Reports**: Automated PDF report delivery
- 🚀 **Scalable Architecture**: Microservices with horizontal scaling

## 🏗️ Architecture


## 📋 Prerequisites

### Development
- Node.js 18+
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker (optional)

### Production
- Kubernetes cluster (AKS/EKS/GKE)
- Azure Container Registry (or Docker Hub)
- PostgreSQL (Azure Database / RDS)
- Redis Cache (Azure Cache / ElastiCache)

## 🚀 Quick Start

### Local Development

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/pesa-analyser.git
cd pesa-analyser

# 2. Set up environment variables
cp .env.example .env
cp frontend/.env.example frontend/.env
cp backend/.env.example backend/.env

# Generate a secret and set NEXTAUTH_SECRET in the root .env file:
openssl rand -base64 48
# Add Google OAuth credentials to frontend/.env if you want Google sign-in.

# 3. Start the complete application
docker compose up --build
```

Open the frontend at http://localhost:3000. The API is at
http://localhost:8000, PostgreSQL is available to desktop pgAdmin on port 15432
(the host port can be changed with `POSTGRES_PORT`),
and Kibana is at http://localhost:5601. This Compose file starts the frontend,
API, PostgreSQL, Redis, Elasticsearch, Kibana, Celery worker, and Celery beat
services. Frontend Prisma/NextAuth tables are kept in the PostgreSQL `nextauth`
schema, separate from the backend's tables in `public`; Compose creates the
schema automatically without dropping existing database tables.

Statement uploads are streamed to shared storage and analyzed by the Celery
worker rather than inside the API request. For production, configure persistent
shared storage for API and worker containers, use managed PostgreSQL/Redis or
secure their credentials, set strong application secrets, and tune worker
concurrency for the available memory. The Kubernetes deployment includes a
separate worker deployment and mounts the same uploads volume.
