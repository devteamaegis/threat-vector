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
        "caller_language": classification.get("caller_language"),
        "multilingual_call": classification.get("multilingual_call"),
        "english_translation": classification.get("english_translation"),
        "gemini_level": classification.get("gemini_level"),
        "gemini_reasoning": classification.get("gemini_reasoning"),
        "consensus": classification.get("consensus"),
        "three_model_consensus": classification.get("three_model_consensus"),
        "bayes_probability_pct": classification.get("bayes_probability_pct"),
        "bayes_ci_low_pct": classification.get("bayes_ci_low_pct"),
        "bayes_ci_high_pct": classification.get("bayes_ci_high_pct"),
        "bayes_top_drivers": classification.get("bayes_top_drivers"),
        "bayes_features_hit": classification.get("bayes_features_hit"),
        "s3_archive_uri": classification.get("s3_archive_uri"),
        "deepgram_confidence": classification.get("deepgram_confidence"),
        "deepgram_language": classification.get("deepgram_language"),
        "cross_school_alert": classification.get("cross_school_alert"),
        "threat_window": classification.get("threat_window"),
        "threat_window_confidence": classification.get("threat_window_confidence"),
        "dispatch_brief": classification.get("dispatch_brief"),
        "osint_findings": classification.get("osint_findings"),
        "prior_tips_context": classification.get("prior_tips_context"),
        "pipeline_errors": classification.get("pipeline_errors"),
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
