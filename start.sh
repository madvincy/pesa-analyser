#!/bin/bash

echo "🚀 Starting Pesa Analyser..."

# Check if PostgreSQL is running
if ! pg_isready -h localhost -U postgres > /dev/null 2>&1; then
    echo "⚠️ PostgreSQL is not running. Starting PostgreSQL..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew services start postgresql
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo service postgresql start || sudo systemctl start postgresql
    fi
    sleep 3
fi

# Check if backend is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "📡 Starting backend..."
    cd backend
    source venv/bin/activate 2>/dev/null || echo "⚠️ Virtual environment not found, using system Python"
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
    BACKEND_PID=$!
    cd ..
    sleep 3
fi

# Start frontend
echo "🎨 Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Pesa Analyser is running!"
echo "📍 Frontend: http://localhost:3000"
echo "📍 Backend: http://localhost:8000"
echo "📍 API Docs: http://localhost:8000/docs"
echo ""
echo "📊 Database: PostgreSQL (pesa_db)"
echo "👤 Admin: Create with: cd frontend && npx tsx scripts/create-admin.ts"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for user to press Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
