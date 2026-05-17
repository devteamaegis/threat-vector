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

SYSTEM_PROMPT = """You are Claudia, the AI school secretary for the Threat Vector system. You handle three types of calls — and you sound like a warm, competent human secretary, not a robot.

## How you speak
Short sentences. Natural pauses. Never sound like you're reading a script. Say "got it" and "okay" and "let me make sure I have that right." If someone is upset, slow down and make them feel heard first.

Never use filler phrases like "Certainly!" or "Of course!" or "Absolutely!" — just speak like a person.

---

## Call type 1: SAFETY TIPS (anonymous threats, safety concerns)
When someone starts describing a threat, danger, or something that scared them:
- Reassure them: "This line is completely anonymous. No one will know you called."
- Gather: which school, what they saw or heard, where on campus, when, any description of the person involved
- End warmly: "Thank you for calling. This gets reviewed by safety staff right away. You did the right thing."
- Never ask for their name.

## Call type 2: ATTENDANCE (parent calling to report absence or tardy)
When a parent says their child is absent, late, or leaving early:
- Confirm: student's full name, grade or homeroom teacher, date, reason (illness, appointment, family matter — no medical details needed)
- Say back what you captured to confirm accuracy
- End: "Got it, I've logged that. [Student name]'s teacher will be notified. Have a good day."

## Call type 3: GENERAL SCHOOL INQUIRIES
When someone has a general question about the school:
- Hours, events, contact info, enrollment questions
- Answer briefly if you know it, or say: "Let me connect you with the main office for that — they'll have the most current information."

---

## How to figure out which call type it is
Listen to the first 10 seconds. If they sound scared or worried — it's a safety tip. If they start with "my son" or "my daughter" — it's probably attendance. If they ask a question — it's a general inquiry. When in doubt, just ask: "Are you reporting a safety concern, or is this about attendance?"

Stay warm and human throughout. Every call matters."""

BEGIN_MESSAGE = "Hi, thanks for calling. This is Claudia — I can help with safety tips, attendance, or general school questions. What can I do for you?"


def get_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def list_voices(api_key: str) -> list:
    """Fetch available TTS voices from AgentPhone."""
    try:
        r = httpx.get(f"{API_BASE}/v1/voices", headers=get_headers(api_key))
        r.raise_for_status()
        return r.json()
    except Exception:
        # Some endpoints use /v1/agents/voices
        try:
            r = httpx.get(f"{API_BASE}/v1/agents/voices", headers=get_headers(api_key))
            r.raise_for_status()
            return r.json()
        except Exception:
            return []


def pick_best_voice(voices: list) -> str | None:
    """Pick the warmest-sounding female voice. Returns voice ID or None."""
    if not voices:
        return None
    # Prefer: female, warm/natural/conversational descriptors, not "professional" or "corporate"
    priority_keywords = ["warm", "natural", "conversational", "friendly", "soft", "calm"]
    female_keywords = ["female", "woman", "girl", "feminine", "she"]
    avoid_keywords = ["robotic", "corporate", "formal", "british"]

    scored = []
    for v in voices:
        name = (v.get("name") or v.get("voiceName") or "").lower()
        desc = (v.get("description") or v.get("style") or "").lower()
        combined = f"{name} {desc}"

        if any(k in combined for k in avoid_keywords):
            continue

        score = 0
        if any(k in combined for k in female_keywords):
            score += 3
        for kw in priority_keywords:
            if kw in combined:
                score += 2

        voice_id = v.get("id") or v.get("voiceId") or v.get("voice_id")
        if voice_id:
            scored.append((score, voice_id, name))

    if scored:
        scored.sort(reverse=True)
        return scored[0][1]
    # Fall back to first voice
    first = voices[0]
    return first.get("id") or first.get("voiceId") or first.get("voice_id")


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

    # Fetch and select voice
    print("\nFetching available voices...")
    voices = list_voices(api_key)
    if voices:
        print(f"  Found {len(voices)} voices:")
        for v in voices[:8]:
            vid = v.get("id") or v.get("voiceId") or v.get("voice_id", "")
            vname = v.get("name") or v.get("voiceName", "")
            vdesc = v.get("description") or v.get("style", "")
            print(f"    {vid}: {vname} — {vdesc}")
        best_voice = pick_best_voice(voices)
        if best_voice:
            print(f"  → Auto-selected voice: {best_voice}")
    else:
        best_voice = None
        print("  Could not fetch voices (will use account default)")

    # Configure agent
    agent_payload = {
        "voiceMode": "hosted",
        "systemPrompt": SYSTEM_PROMPT,
        "beginMessage": BEGIN_MESSAGE,
        "modelTier": "max",
    }
    if best_voice:
        agent_payload["voiceId"] = best_voice

    print(f"\nConfiguring agent {agent_id}...")
    updated = update_agent(api_key, agent_id, agent_payload)
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
