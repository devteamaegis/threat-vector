from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import os
import time
from pathlib import Path
from dotenv import load_dotenv

# Always load .env relative to this file, regardless of cwd
load_dotenv(Path(__file__).parent / ".env", override=True)

from agent import run_threat_agent
from live_call_simulator import stream_live_call, get_demo_transcript
from cross_school_detector import get_district_threat_summary

app = FastAPI(title="Threat Vector", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_call_fields(body: dict) -> tuple[str, str, str, str]:
    """
    Normalize payload from AgentPhone webhook events.

    AgentPhone event format:
      { "event": "agent.call_ended", "call": { "id", "transcript", "status" } }
    Also handles flat format and direct test POSTs.
    """
    event_type = body.get("event") or body.get("type") or ""

    # Prefer nested call object; fall back to top-level body
    call = body.get("call", body)

    call_id = (
        call.get("id")
        or call.get("call_id")
        or body.get("id")
        or body.get("call_id")
        or "unknown"
    )
    transcript = (
        call.get("transcript")
        or call.get("transcription")
        or body.get("transcript")
        or ""
    )
    recording_url = (
        call.get("recording_url")
        or call.get("recordingUrl")
        or call.get("recording")
        or body.get("recording_url")
        or body.get("recordingUrl")
        or ""
    )
    # Treat event type as the status signal
    status = event_type or call.get("status") or body.get("status") or ""
    return str(call_id), str(transcript), str(status).lower(), str(recording_url)


CALL_ENDED_EVENTS = {
    "agent.call_ended",
    "call.ended",
    "call.completed",
    "completed",
    "ended",
}


# AgentPhone primary webhook path
@app.post("/webhook/call")
async def handle_call(request: Request):
    body = await request.json()
    call_id, transcript, status, recording_url = _extract_call_fields(body)

    print(f"[webhook] event={status!r} call_id={call_id!r} transcript_len={len(transcript)}")

    if status in CALL_ENDED_EVENTS and transcript.strip():
        asyncio.create_task(run_threat_agent(call_id, transcript, recording_url or None))
        return JSONResponse({"status": "processing", "call_id": call_id})

    return JSONResponse({
        "status": "received",
        "call_id": call_id,
        "event": status,
        "skipped": not transcript.strip(),
    })


# AgentPhone may also POST to /webhook/agentphone
@app.post("/webhook/agentphone")
async def handle_agentphone(request: Request):
    return await handle_call(request)


# Manual trigger for demo / testing without AgentPhone
@app.post("/webhook/test")
async def handle_test(request: Request):
    body = await request.json()
    call_id   = body.get("call_id", "manual-test")
    transcript = body.get("transcript", "")
    recording_url = body.get("recording_url")
    if not transcript.strip():
        return JSONResponse({"error": "transcript required"}, status_code=400)
    asyncio.create_task(run_threat_agent(call_id, transcript, recording_url))
    return JSONResponse({"status": "processing", "call_id": call_id})


@app.post("/api/demo-live-call")
async def demo_live_call(request: Request):
    """Start a live call simulation for demo purposes."""
    body = await request.json()
    transcript = body.get("transcript") or get_demo_transcript()
    call_id = body.get("call_id", f"demo-{int(time.time())}")
    school = body.get("school", "Westview High School")
    delay_ms = body.get("delay_ms", 150)
    asyncio.create_task(stream_live_call(call_id, transcript, school, delay_ms))
    return JSONResponse({"status": "streaming", "call_id": call_id})


@app.get("/api/cross-school-alerts")
async def cross_school_alerts():
    """Return district-wide threat pattern summary."""
    summary = get_district_threat_summary(days=7)
    return JSONResponse(summary)


@app.get("/api/sponge/wallet")
async def sponge_wallet():
    """Return Sponge wallet balance and recent agent payment transactions."""
    from sponge_payments import get_wallet_balance, get_recent_transactions
    balance = get_wallet_balance()
    transactions = get_recent_transactions()
    return JSONResponse({"balance": balance, "transactions": transactions})


@app.get("/health")
async def health():
    """Show which integrations are configured."""
    def cfg(key: str) -> bool:
        v = os.getenv(key, "")
        return bool(v) and v not in ("FILL_IN", "+1XXXXXXXXXX")

    return {
        "status": "ok",
        "integrations": {
            "anthropic":    cfg("ANTHROPIC_API_KEY"),
            "supabase":     cfg("SUPABASE_URL"),
            "twilio":       cfg("TWILIO_ACCOUNT_SID"),
            "agentphone":   cfg("AGENTPHONE_API_KEY"),
            "agentmail":    cfg("AGENTMAIL_API_KEY"),
            "supermemory":  cfg("SUPERMEMORY_API_KEY"),
            "moss":         cfg("MOSS_API_KEY"),
            "stripe":       cfg("STRIPE_SECRET_KEY"),
            "sponge":       cfg("SPONGE_API_KEY"),
            "aws":          cfg("AWS_ACCESS_KEY_ID"),
            "gemini":       cfg("GOOGLE_API_KEY"),
            "deepgram":     cfg("DEEPGRAM_API_KEY"),
        }
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
