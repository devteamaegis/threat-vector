from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Always load .env relative to this file, regardless of cwd
load_dotenv(Path(__file__).parent / ".env", override=True)

from agent import run_threat_agent

app = FastAPI(title="Threat Vector", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_call_fields(body: dict) -> tuple[str, str, str]:
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
    # Treat event type as the status signal
    status = event_type or call.get("status") or body.get("status") or ""
    return str(call_id), str(transcript), str(status).lower()


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
    call_id, transcript, status = _extract_call_fields(body)

    print(f"[webhook] event={status!r} call_id={call_id!r} transcript_len={len(transcript)}")

    if status in CALL_ENDED_EVENTS and transcript.strip():
        asyncio.create_task(run_threat_agent(call_id, transcript))
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
    if not transcript.strip():
        return JSONResponse({"error": "transcript required"}, status_code=400)
    asyncio.create_task(run_threat_agent(call_id, transcript))
    return JSONResponse({"status": "processing", "call_id": call_id})


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
        }
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
