#!/bin/bash
set -e

echo "Starting Prometheus v4 services..."

# Shared infrastructure
docker-compose up -d

# Backend microservices (each in its own directory context)
(cd classification && uvicorn main:app --port 8001 --reload) &
(cd regression && uvicorn main:app --port 8002 --reload) &
(cd multiclassification && uvicorn main:app --port 8003 --reload) &
(cd timeseries && uvicorn main:app --port 8004 --reload) &
(cd gateway && uvicorn main:app --port 8000 --reload) &

# Celery worker (from project root — handles all task queues)
celery -A celery_app worker --loglevel=info &

# Frontend
(cd frontend && npm run dev) &

echo ""
echo "All Prometheus services starting up..."
echo ""
echo "Frontend:            http://localhost:3000"
echo "Gateway:             http://localhost:8000"
echo "Classification:      http://localhost:8001"
echo "Regression:          http://localhost:8002"
echo "Multiclassification: http://localhost:8003"
echo "Timeseries:          http://localhost:8004"
echo ""
echo "Press Ctrl+C to stop all services."

wait
