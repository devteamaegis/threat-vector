from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import os
import time as _time
import json as _json
import requests as _requests
from pathlib import Path
from dotenv import load_dotenv

# Always load .env relative to this file, regardless of cwd
load_dotenv(Path(__file__).parent / ".env", override=True)

from agent import run_threat_agent
from live_call_simulator import stream_live_call, get_demo_transcript
from cross_school_detector import get_district_threat_summary
from counselor_notes import log_counselor_note, check_escalation_pattern
from notify import send_sms_alert


# ── AgentPhone transcript fetcher ─────────────────────────────────────────────

def _agentphone_fetch_transcript(call_id: str) -> tuple[str, int]:
    """
    Fetch the actual transcript from AgentPhone API using the call ID.
    Returns (user_transcript, duration_seconds).
    The webhook sends transcripts:[] but the REST API has the real data.
    """
    api_key = os.getenv("AGENTPHONE_API_KEY", "")
    if not api_key or call_id in ("unknown", ""):
        return "", 0
    try:
        resp = _requests.get(
            f"https://api.agentphone.ai/v1/calls/{call_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=8,
        )
        if resp.status_code != 200:
            print(f"[AgentPhone API] {resp.status_code}: {resp.text[:200]}")
            return "", 0
        data = resp.json()
        duration = int(data.get("durationSeconds") or data.get("duration_seconds") or 0)
        # Build transcript from user's side only (transcript field in each entry)
        parts = []
        for t in (data.get("transcripts") or []):
            user_text = (t.get("transcript") or "").strip()
            if user_text:
                parts.append(user_text)
        # Deduplicate consecutive duplicates (AgentPhone sends incremental updates)
        deduped = []
        for p in parts:
            if not deduped or p != deduped[-1]:
                deduped.append(p)
        # Use the last/longest version of each utterance
        full_transcript = " ".join(deduped).strip()
        return full_transcript, duration
    except Exception as e:
        print(f"[AgentPhone API] fetch failed: {e}")
        return "", 0

app = FastAPI(title="Threat Vector", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_call_fields(body: dict) -> tuple[str, str, str, str, int, dict | None]:
    """
    Normalize payload from AgentPhone webhook events.

    Confirmed AgentPhone format (from live webhook logs):
      {
        "event": "agent.call_ended",
        "channel": "voice",
        "data": {
          "callId": "cmpacgtfi...",
          "durationSeconds": 8.86,
          "transcript": [{"role": "user", "content": "I want to harm you. "}],
          "status": "completed",
          "recording_url": null
        }
      }
    Also handles flat format and direct test POSTs.
    """
    event_type = body.get("event") or body.get("type") or ""

    # AgentPhone nests everything under "data"; fall back to "call" or top-level body
    data = body.get("data") or body.get("call") or body

    # ── call_id ────────────────────────────────────────────────────────────────
    call_id = (
        data.get("callId")
        or data.get("id")
        or data.get("call_id")
        or body.get("callId")
        or body.get("id")
        or body.get("call_id")
        or "unknown"
    )

    # ── transcript ─────────────────────────────────────────────────────────────
    # For agent.call_ended: transcript is a list of {role, content} dicts.
    # For agent.message: transcript is a plain string.
    raw_transcript = data.get("transcript") or body.get("transcript") or data.get("transcription") or ""
    if isinstance(raw_transcript, list):
        # Join only user-role utterances (filter out AI responses)
        user_parts = [
            t.get("content", "").strip()
            for t in raw_transcript
            if isinstance(t, dict) and t.get("role") == "user" and t.get("content", "").strip()
        ]
        transcript = " ".join(user_parts)
    else:
        transcript = str(raw_transcript).strip()

    # ── recording_url ──────────────────────────────────────────────────────────
    recording_url = (
        data.get("recording_url")
        or data.get("recordingUrl")
        or data.get("recording")
        or body.get("recording_url")
        or body.get("recordingUrl")
        or ""
    )

    # ── duration ───────────────────────────────────────────────────────────────
    # AgentPhone uses "durationSeconds" (float) inside the data object
    raw_dur = (
        data.get("durationSeconds")
        or data.get("duration_seconds")
        or data.get("duration")
        or body.get("duration_seconds")
        or body.get("duration")
        or body.get("call_duration_seconds")
        or 0
    )
    try:
        call_duration = int(float(str(raw_dur)))
    except (ValueError, TypeError):
        call_duration = 0
    # Estimate from word count if still zero and we have a transcript
    if call_duration == 0 and transcript.strip():
        call_duration = max(5, len(transcript.split()) // 2)

    # ── status / event ─────────────────────────────────────────────────────────
    status = event_type or data.get("status") or body.get("status") or ""
    caller_location = (
        data.get("location")
        or data.get("caller_location")
        or data.get("geo")
        or body.get("location")
        or body.get("caller_location")
    )
    if not caller_location:
        lat = data.get("call_lat") or data.get("lat") or data.get("latitude") or body.get("call_lat") or body.get("lat") or body.get("latitude")
        lng = data.get("call_lng") or data.get("lng") or data.get("lon") or data.get("longitude") or body.get("call_lng") or body.get("lng") or body.get("lon") or body.get("longitude")
        if lat is not None and lng is not None:
            caller_location = {"lat": lat, "lng": lng}
    return str(call_id), str(transcript), str(status).lower(), str(recording_url), call_duration, caller_location


CALL_ENDED_EVENTS = {
    "agent.call_ended",
    "call.ended",
    "call.completed",
    "completed",
    "ended",
}


# AgentPhone primary webhook path
async def _process_real_call(call_id: str, transcript: str, recording_url: str, call_duration: int, caller_location: dict | None = None):
    """
    Wait briefly for AgentPhone to finalize transcript, then fetch via API
    if the webhook delivered an empty transcript, then run the full pipeline.
    """
    if not transcript.strip() and call_id != "unknown":
        print(f"[{call_id}] Transcript empty in webhook — fetching from AgentPhone API...")
        await asyncio.sleep(3)  # Give AgentPhone 3s to finalize
        transcript, api_duration = await asyncio.to_thread(_agentphone_fetch_transcript, call_id)
        if api_duration > 0 and call_duration == 0:
            call_duration = api_duration
        print(f"[{call_id}] API transcript: {len(transcript)} chars, duration={call_duration}s")

    if not transcript.strip():
        print(f"[{call_id}] No transcript available — skipping pipeline")
        return

    # Estimate duration from word count if still 0
    if call_duration == 0:
        call_duration = max(5, len(transcript.split()) // 2)

    school_guess = next(
        (w for w in transcript.split() if len(w) > 4 and w[0].isupper()), "Unknown School"
    )
    await stream_live_call(call_id, transcript, school_guess, delay_ms=80)
    await run_threat_agent(call_id, transcript, recording_url or None, call_duration, caller_location)


@app.post("/webhook/call")
async def handle_call(request: Request):
    body = await request.json()
    print(f"[webhook RAW] {_json.dumps(body)[:1000]}")

    call_id, transcript, status, recording_url, call_duration, caller_location = _extract_call_fields(body)
    print(f"[webhook] event={status!r} call_id={call_id!r} duration={call_duration}s transcript_len={len(transcript)}")

    if status in CALL_ENDED_EVENTS:
        asyncio.create_task(_process_real_call(call_id, transcript, recording_url or "", call_duration, caller_location))
        return JSONResponse({"status": "processing", "call_id": call_id})

    return JSONResponse({
        "status": "received",
        "call_id": call_id,
        "event": status,
        "skipped": status not in CALL_ENDED_EVENTS,
    })


# AgentPhone may also POST to /webhook/agentphone
@app.post("/webhook/agentphone")
async def handle_agentphone(request: Request):
    return await handle_call(request)


@app.post("/webhook/sms")
async def handle_sms(request: Request):
    """Twilio/AgentPhone SMS webhook — routes to same pipeline as voice calls."""
    body = await request.body()
    # Twilio sends form-encoded data
    import urllib.parse
    params = dict(urllib.parse.parse_qsl(body.decode()))
    from_number = params.get("From", "unknown")
    sms_body = params.get("Body", "")
    # Mask phone number for privacy
    masked = from_number[:3] + "****" + from_number[-2:] if len(from_number) > 5 else "unknown"

    if not sms_body.strip():
        return JSONResponse({"status": "empty"})

    import uuid
    call_id = f"sms-{uuid.uuid4().hex[:10]}"
    print(f"[{call_id}] Inbound SMS from {masked}: {sms_body[:80]}")

    asyncio.create_task(run_threat_agent(
        call_id=call_id,
        transcript=sms_body,
        recording_url=None,
        call_duration_seconds=max(3, len(sms_body.split()) // 2),
        caller_location=None,
    ))

    # Twilio expects TwiML response
    from fastapi.responses import Response
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response><Message>Your tip has been received anonymously. Thank you for keeping your school safe.</Message></Response>',
        media_type="application/xml"
    )


# Manual trigger for demo / testing without AgentPhone
@app.post("/webhook/test")
async def handle_test(request: Request):
    body = await request.json()
    call_id       = body.get("call_id", "manual-test")
    transcript    = body.get("transcript", "")
    recording_url = body.get("recording_url")
    call_duration = int(body.get("call_duration_seconds", max(5, len(transcript.split()) // 2)))
    caller_location = body.get("caller_location")
    if not caller_location and body.get("call_lat") is not None and body.get("call_lng") is not None:
        caller_location = {"lat": body.get("call_lat"), "lng": body.get("call_lng")}
    if not transcript.strip():
        return JSONResponse({"error": "transcript required"}, status_code=400)
    asyncio.create_task(run_threat_agent(call_id, transcript, recording_url, call_duration, caller_location))
    return JSONResponse({"status": "processing", "call_id": call_id})


@app.post("/api/demo-live-call")
async def demo_live_call(request: Request):
    """Start a live call simulation for demo purposes."""
    body = await request.json()
    transcript = body.get("transcript") or get_demo_transcript()
    call_id = body.get("call_id", f"demo-{int(_time.time())}")
    school = body.get("school", "Westview High School")
    delay_ms = body.get("delay_ms", 150)
    asyncio.create_task(stream_live_call(call_id, transcript, school, delay_ms))
    return JSONResponse({"status": "streaming", "call_id": call_id})


@app.post("/api/counselor/note")
async def counselor_note(request: Request):
    body = await request.json()
    school_name      = body.get("school_name", "")
    student_id_hash  = body.get("student_id_hash", "")
    note_text        = body.get("note_text", "")
    severity         = body.get("severity", "medium")
    staff_id         = body.get("staff_id", "")

    if not school_name or not student_id_hash or not note_text:
        return JSONResponse({"error": "school_name, student_id_hash, and note_text are required"}, status_code=400)

    log_counselor_note(school_name, student_id_hash, note_text, severity, staff_id)
    escalation = check_escalation_pattern(school_name, student_id_hash)

    if escalation.get("escalate"):
        call_id = f"counselor-{student_id_hash[:8]}"
        classification = {
            "threat_level": 4,
            "school_name": school_name,
            "summary": escalation["reason"],
            "recommended_action": "escalate",
            "threat_type": "counselor_escalation",
        }
        try:
            send_sms_alert(
                {
                    **classification,
                    "summary": f"COUNSELOR ESCALATION: {escalation['reason']}",
                },
                call_id,
            )
        except Exception as e:
            print(f"[counselor] WARNING: SMS escalation failed: {e}")

    return JSONResponse({
        "status": "logged",
        "escalate": escalation.get("escalate", False),
        "tip_count": escalation.get("tip_count", 0),
        "note_count": escalation.get("note_count", 0),
        "reason": escalation.get("reason", ""),
    })


@app.post("/api/tip/submit")
async def submit_tip(request: Request):
    body = await request.json()
    transcript   = body.get("transcript", "")
    school_name  = body.get("school_name", "")
    category     = body.get("category", "other")
    tip_source   = body.get("tip_source", "web_form")

    if not transcript.strip():
        return JSONResponse({"error": "transcript is required"}, status_code=400)

    import uuid
    call_id = f"{tip_source}-{uuid.uuid4().hex[:12]}"
    call_duration_seconds = max(5, len(transcript.split()) // 2)

    asyncio.create_task(run_threat_agent(call_id, transcript, None, call_duration_seconds, None))
    return JSONResponse({"status": "received", "call_id": call_id})


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


@app.post("/api/demo/background-check")
async def demo_background_check(request: Request):
    """
    Run a real Sponge-paid background check for a named subject.
    Uses multi-source search: DuckDuckGo + CourtListener + Bing + Browser-Use.
    Used by the Kairos dashboard Wallet tab Demo Check button.
    """
    body = await request.json()
    subject_name = body.get("subject", "Ishaan Samantray")
    school = body.get("school", "YC Demo")
    threat_level = int(body.get("threat_level", 3))
    call_id = body.get("call_id", f"demo-{int(_time.time())}")

    from sponge_payments import authorize_background_check, log_transaction_to_supabase
    from background_check import run_real_background_check

    # 1. Authorize Sponge micropayment
    receipt = await asyncio.to_thread(authorize_background_check, subject_name, school, call_id, threat_level)

    # 2. Run real multi-source background check
    findings = await run_real_background_check(subject_name, school, call_id, threat_level)

    # 3. Log to Supabase sponge_transactions
    await asyncio.to_thread(
        log_transaction_to_supabase,
        {**receipt, "findings_summary": f"Subject: {subject_name}. {findings.get('abstract', '')[:400]}"},
        call_id,
    )

    return JSONResponse({**receipt, "findings": findings, "check_complete": True})


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
