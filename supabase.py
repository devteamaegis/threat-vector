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
        "call_duration_seconds": classification.get("call_duration_seconds"),
        "caller_emotion": classification.get("caller_emotion"),
        "caller_tone": classification.get("caller_tone"),
        "escalation_risk": classification.get("escalation_risk"),
        "credibility_signals": classification.get("credibility_signals"),
        "key_facts": classification.get("key_facts"),
    }

    district_id = os.getenv("NEXT_PUBLIC_DISTRICT_ID")
    if district_id:
        payload["district_id"] = district_id

    # Base columns guaranteed to exist in schema
    BASE_COLUMNS = {
        "description", "category", "urgency", "severity", "status",
        "is_anonymous", "ai_summary", "ai_triage_score", "ai_recommended_action",
        "school_name", "created_at", "submitted_at",
    }

    def _post(data):
        return requests.post(
            f"{SUPABASE_URL}/rest/v1/tips",
            headers=_headers(),
            json=data,
            timeout=10,
        )

    try:
        response = _post(payload)
        if response.status_code in (200, 201):
            data = response.json()
            tip_id = data[0].get("id") if data else None
            print(f"[{call_id}] Supabase: tip logged with full schema (id: {tip_id})")
            return tip_id

        # Extended columns not migrated yet — retry with base columns only
        if response.status_code == 400 and "column" in response.text.lower():
            print(f"[{call_id}] Supabase: extended columns missing — retrying with base schema")
            base_payload = {k: v for k, v in payload.items() if k in BASE_COLUMNS and v is not None}
            response2 = _post(base_payload)
            if response2.status_code in (200, 201):
                data = response2.json()
                tip_id = data[0].get("id") if data else None
                print(f"[{call_id}] Supabase: tip logged with base schema (id: {tip_id})")
                return tip_id
            print(f"[{call_id}] WARNING: Supabase base retry failed {response2.status_code}: {response2.text[:200]}")
            return None

        print(f"[{call_id}] WARNING: Supabase returned {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"[{call_id}] WARNING: Supabase log failed: {e}")
    return None

def update_tip_enriched(tip_id: str | None, call_id: str, fields: dict) -> bool:
    """PATCH an existing tip row with enrichment data from parallel pipeline steps."""
    if not tip_id or not SUPABASE_URL or not SUPABASE_KEY:
        return False
    payload = {k: v for k, v in fields.items() if v is not None}
    if not payload:
        return False
    try:
        response = requests.patch(
            f"{SUPABASE_URL}/rest/v1/tips",
            params={"id": f"eq.{tip_id}"},
            headers={**_headers(), "Prefer": "return=minimal"},
            json=payload,
            timeout=10,
        )
        if response.status_code in (200, 204):
            print(f"[{call_id}] Supabase: tip enriched (fields: {list(payload.keys())})")
            return True
        print(f"[{call_id}] WARNING: Supabase enrich failed {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"[{call_id}] WARNING: Supabase enrich failed: {e}")
    return False


def update_tip_geo(tip_id: str | None, call_id: str, call_lat: float | None, call_lng: float | None, location_context: str | None):
    if not tip_id or not SUPABASE_URL or not SUPABASE_KEY:
        return False
    payload = {
        "call_lat": call_lat,
        "call_lng": call_lng,
        "location_context": location_context,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    if not payload:
        return False
    try:
        response = requests.patch(
            f"{SUPABASE_URL}/rest/v1/tips",
            params={"id": f"eq.{tip_id}"},
            headers={**_headers(), "Prefer": "return=minimal"},
            json=payload,
            timeout=8,
        )
        if response.status_code in (200, 204):
            print(f"[{call_id}] Supabase: GPS/location context updated")
            return True
        print(f"[{call_id}] WARNING: Supabase GPS update failed {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"[{call_id}] WARNING: Supabase GPS update failed: {e}")
    return False
