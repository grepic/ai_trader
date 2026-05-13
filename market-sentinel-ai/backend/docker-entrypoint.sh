#!/bin/sh
set -e

echo "============================================================"
echo "Market Sentinel AI — starting up"
echo "============================================================"

echo "Running database migrations..."
alembic upgrade head

echo "Migrations complete. Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
