#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "🚀 Starting AlphaSight..."
docker-compose up -d

echo "⏳ Waiting for backend to become healthy..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        echo "✅ Backend is healthy!"
        break
    fi
    sleep 2
done

echo ""
echo "============================================"
echo "  AlphaSight is live."
echo "  Dashboard: http://localhost:3000"
echo "  Paper trading with \$100,000 simulated capital"
echo "  Add real funds at https://app.alpaca.markets"
echo "============================================"
