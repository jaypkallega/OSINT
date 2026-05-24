#!/bin/bash
# OSINT Privacy Intelligence - Quick Start Script
# This script starts both backend and frontend services

echo "🔍 OSINT Privacy Intelligence App"
echo "=================================="
echo ""

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠️  Redis is not running. Starting Redis..."
    redis-server --daemonize yes
    sleep 2
fi

# Check if backend is already running
if curl -s http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
    echo "✅ Backend already running on port 8000"
else
    echo "🚀 Starting backend server..."
    cd "$(dirname "$0")"
    uvicorn main:app --host 127.0.0.1 --port 8000 &
    BACKEND_PID=$!
    sleep 3
    
    if curl -s http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
        echo "✅ Backend started successfully (PID: $BACKEND_PID)"
    else
        echo "❌ Failed to start backend"
        exit 1
    fi
fi

# Check if frontend is already running
if curl -s http://127.0.0.1:8501 > /dev/null 2>&1; then
    echo "✅ Frontend already running on port 8501"
else
    echo "🎨 Starting Streamlit dashboard..."
    streamlit run dashboard.py --server.address localhost --server.port 8501 &
    FRONTEND_PID=$!
    sleep 5
    
    if curl -s http://127.0.0.1:8501 > /dev/null 2>&1; then
        echo "✅ Frontend started successfully (PID: $FRONTEND_PID)"
    else
        echo "⚠️  Frontend may still be starting..."
    fi
fi

echo ""
echo "=================================="
echo "📍 Access Points:"
echo "   Frontend: http://localhost:8501"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "=================================="
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for interrupt
trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT

# Keep script running
wait
