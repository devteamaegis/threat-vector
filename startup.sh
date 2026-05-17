#!/bin/bash
# Threat Vector — start everything for demo
# Usage: ./startup.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║        THREAT VECTOR — STARTUP               ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 1. Check .env exists
if [ ! -f ".env" ]; then
  echo "❌  No .env found. Copy .env.example → .env and fill in keys."
  exit 1
fi

# 2. Install Python deps if needed
if ! python -c "import fastapi" 2>/dev/null; then
  echo "📦  Installing Python dependencies..."
  pip install -r requirements.txt -q
fi

# 3. Start Python backend
echo "🐍  Starting FastAPI backend on http://localhost:8000 ..."
python main.py &
BACKEND_PID=$!
echo "    PID: $BACKEND_PID"

sleep 2

# 4. Show integration status
echo ""
echo "🔍  Integration status:"
curl -s http://localhost:8001/health | python -c "
import sys, json
d = json.load(sys.stdin)
for k, v in d.get('integrations', {}).items():
    icon = '✅' if v else '⚠️ '
    print(f'    {icon}  {k}')
"

# 5. Start dashboard
DASHBOARD_DIR="$(dirname "$SCRIPT_DIR")/threat-vector-dashboard"
if [ -d "$DASHBOARD_DIR" ]; then
  echo ""
  echo "🖥️   Starting dashboard on http://localhost:3002 ..."
  cd "$DASHBOARD_DIR"
  npm run dev -- -p 3002 &
  DASH_PID=$!
  echo "    PID: $DASH_PID"
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Backend:   http://localhost:8001            ║"
echo "║  Dashboard: http://localhost:3002            ║"
echo "║  Health:    http://localhost:8001/health     ║"
echo "║  Test tip:  curl -X POST localhost:8001/webhook/test \\"
echo "║    -H 'Content-Type: application/json' \\"
echo "║    -d '{\"transcript\":\"...\"}' ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "Press Ctrl+C to stop all services."

# Wait and clean up on exit
trap "echo ''; echo 'Shutting down...'; kill $BACKEND_PID 2>/dev/null; kill $DASH_PID 2>/dev/null" EXIT
wait
