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
cp frontend/.env.example frontend/.env.local
cp backend/.env.example backend/.env

# 3. Start with Docker Compose
docker-compose up -d

# Or run separately:

# Frontend
cd frontend
npm install
npm run dev

# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# 4. Open http://localhost:3000
