#!/usr/bin/env python3
"""
Configure the AgentPhone agent for Threat Vector.

Usage:
  python setup_agentphone.py                    # reads NGROK_URL from .env
  python setup_agentphone.py https://abc.ngrok.io  # pass ngrok URL directly

Requires in .env:
  AGENTPHONE_API_KEY=<your key>
  AGENTPHONE_AGENT_ID=<your agent id>   (optional — lists agents if missing)
  NGROK_URL=https://<id>.ngrok.io       (or pass as CLI arg)
"""

import sys
import os
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

API_BASE = "https://api.agentphone.ai"

SYSTEM_PROMPT = """You are Claudia, an anonymous school safety tip intake agent for the Threat Vector system.

Your job is to calmly and professionally gather threat reports from callers. You will:
1. Greet the caller and reassure them this line is completely anonymous
2. Ask what school the concern is about
3. Ask them to describe the threat or concern in detail
4. Ask if there is a specific location within the school
5. Ask about the timeline — is this happening right now, today, or in the coming days?
6. Ask for a description of any person involved, if applicable
7. Thank them and let them know their report will be reviewed by trained safety staff immediately

Keep your tone calm, professional, and non-judgmental. Never ask for the caller's name or any identifying information. If the caller seems panicked, slow down and reassure them. Keep each question brief. End the call gracefully once you have the key details."""

BEGIN_MESSAGE = "Thank you for calling the anonymous school safety tip line. This call is completely confidential. I'm here to help. Please tell me — what school is your concern about, and what did you witness or hear?"


def get_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def list_agents(api_key: str) -> list:
    r = httpx.get(f"{API_BASE}/v1/agents", headers=get_headers(api_key))
    r.raise_for_status()
    return r.json()


def list_numbers(api_key: str) -> list:
    r = httpx.get(f"{API_BASE}/v1/numbers", headers=get_headers(api_key))
    r.raise_for_status()
    return r.json()


def get_webhooks(api_key: str) -> dict:
    r = httpx.get(f"{API_BASE}/v1/webhooks", headers=get_headers(api_key))
    r.raise_for_status()
    return r.json()


def set_account_webhook(api_key: str, webhook_url: str) -> dict:
    r = httpx.post(
        f"{API_BASE}/v1/webhooks",
        headers=get_headers(api_key),
        json={"url": webhook_url},
    )
    r.raise_for_status()
    return r.json()


def set_agent_webhook(api_key: str, agent_id: str, webhook_url: str) -> dict:
    r = httpx.post(
        f"{API_BASE}/v1/agents/{agent_id}/webhook",
        headers=get_headers(api_key),
        json={"url": webhook_url},
    )
    r.raise_for_status()
    return r.json()


def update_agent(api_key: str, agent_id: str, payload: dict) -> dict:
    r = httpx.patch(
        f"{API_BASE}/v1/agents/{agent_id}",
        headers=get_headers(api_key),
        json=payload,
    )
    r.raise_for_status()
    return r.json()


def test_webhook(api_key: str) -> dict:
    r = httpx.post(f"{API_BASE}/v1/webhooks/test", headers=get_headers(api_key))
    r.raise_for_status()
    return r.json()


def main():
    api_key = os.getenv("AGENTPHONE_API_KEY", "")
    agent_id = os.getenv("AGENTPHONE_AGENT_ID", "")
    ngrok_url = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("NGROK_URL", "")).rstrip("/")

    # Validate inputs
    if not api_key or api_key == "FILL_IN":
        print("ERROR: Set AGENTPHONE_API_KEY in .env")
        sys.exit(1)

    if not ngrok_url or "your-ngrok-url" in ngrok_url:
        print("ERROR: Pass your ngrok URL as argument or set NGROK_URL in .env")
        print("  python setup_agentphone.py https://abc123.ngrok.io")
        sys.exit(1)

    webhook_url = f"{ngrok_url}/webhook/agentphone"
    print(f"\nWebhook URL: {webhook_url}")

    # List agents if no agent ID
    if not agent_id or agent_id == "FILL_IN":
        print("\nListing agents (no AGENTPHONE_AGENT_ID set)...")
        agents = list_agents(api_key)
        print(json.dumps(agents, indent=2))
        if agents:
            agent_id = agents[0].get("id") or agents[0].get("agentId", "")
            print(f"\nUsing first agent: {agent_id}")
            print(f"Add this to .env:  AGENTPHONE_AGENT_ID={agent_id}")
        else:
            print("No agents found. Create one in the AgentPhone dashboard first.")
            sys.exit(1)

    # Show numbers
    print("\nPhone numbers on account:")
    try:
        numbers = list_numbers(api_key)
        for n in numbers:
            print(f"  {n.get('number') or n.get('phoneNumber')}  (id: {n.get('id')})")
    except Exception as e:
        print(f"  Could not list numbers: {e}")

    # Configure agent
    print(f"\nConfiguring agent {agent_id}...")
    updated = update_agent(api_key, agent_id, {
        "voiceMode": "hosted",
        "systemPrompt": SYSTEM_PROMPT,
        "beginMessage": BEGIN_MESSAGE,
        "modelTier": "balanced",
    })
    print(f"  Agent updated: {updated.get('name') or updated.get('id')}")

    # Set agent-level webhook
    print(f"\nSetting webhook → {webhook_url}")
    try:
        wh = set_agent_webhook(api_key, agent_id, webhook_url)
        print(f"  Agent webhook set: {wh}")
    except Exception:
        # Fall back to account-level webhook
        print("  Agent webhook failed — trying account-level webhook...")
        wh = set_account_webhook(api_key, webhook_url)
        print(f"  Account webhook set: {wh}")

    # Test connectivity
    print("\nTesting webhook connectivity...")
    try:
        test = test_webhook(api_key)
        print(f"  Test result: {test}")
    except Exception as e:
        print(f"  Test failed (backend may not be running): {e}")

    print("\n✓ AgentPhone configured. Call +12402665263 to test.")
    print(f"  Your backend must be running at port 8001 with ngrok forwarding to it.")


if __name__ == "__main__":
    main()
