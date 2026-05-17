#!/bin/bash
# Start the backend + ngrok, then auto-configure AgentPhone
# Usage: ./start_with_ngrok.sh

set -e
PORT=8001

echo "Starting Threat Vector backend on port $PORT..."
python main.py &
BACKEND_PID=$!
sleep 2

echo "Starting ngrok tunnel..."
ngrok http $PORT --log=stdout --log-format=json > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!
sleep 3

# Extract public URL from ngrok API
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])" 2>/dev/null)

if [ -z "$NGROK_URL" ]; then
    echo "ERROR: Could not get ngrok URL. Is ngrok installed?"
    kill $BACKEND_PID $NGROK_PID 2>/dev/null
    exit 1
fi

echo ""
echo "==========================================="
echo "  ngrok URL: $NGROK_URL"
echo "  Webhook:   $NGROK_URL/webhook/agentphone"
echo "==========================================="
echo ""

# Update .env with the ngrok URL
sed -i.bak "s|NGROK_URL=.*|NGROK_URL=$NGROK_URL|" .env
echo "Updated .env with NGROK_URL=$NGROK_URL"

# Configure AgentPhone
echo "Configuring AgentPhone agent..."
python setup_agentphone.py "$NGROK_URL"

echo ""
echo "Ready! Call +12402665263 to test Threat Vector."
echo ""
echo "Press Ctrl+C to stop."
wait $BACKEND_PID
