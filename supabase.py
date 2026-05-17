import os
import requests
from datetime import datetime

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def log_tip_to_aegis(classification: dict, transcript: str, call_id: str, osint_summary: str):
    if not SUPABASE_URL or not SUPABASE_KEY:
        print(f"[{call_id}] WARNING: Supabase credentials not set — skipping DB log")
        return None

    level = classification.get("threat_level", 3)
    urgency_map = {1: "low", 2: "low", 3: "medium", 4: "high", 5: "critical"}
    severity_map = {1: "low", 2: "low", 3: "medium", 4: "high", 5: "critical"}

    # Build ai_summary with OSINT context if available
    summary = classification.get("summary", "")
    if osint_summary and "skipping" not in osint_summary.lower():
        summary += f" [OSINT: {osint_summary[:150]}]"

    payload = {
        "description": transcript,
        "category": classification.get("threat_type", "other"),
        "urgency": urgency_map.get(level, "medium"),
        "severity": severity_map.get(level, "medium"),
        "status": "new",
        "is_anonymous": True,
        "ai_summary": summary,
        "ai_triage_score": level * 2,           # scale 1-5 → 2-10
        "ai_recommended_action": classification.get("recommended_action", "monitor"),
        "school_name": classification.get("school_name"),
    }

    district_id = os.getenv("NEXT_PUBLIC_DISTRICT_ID")
    if district_id:
        payload["district_id"] = district_id

    try:
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/tips",
            headers=_headers(),
            json=payload,
            timeout=10
        )
        if response.status_code in (200, 201):
            data = response.json()
            return data[0].get("id") if data else None
        print(f"[{call_id}] WARNING: Supabase returned {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"[{call_id}] WARNING: Supabase log failed: {e}")
    return None
