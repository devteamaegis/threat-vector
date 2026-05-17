import os
import requests
from datetime import datetime, timezone

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def log_counselor_note(
    school_name: str,
    student_id_hash: str,
    note_text: str,
    severity: str,
    staff_id: str,
) -> dict | None:
    """Write a counselor note to the counselor_notes Supabase table."""
    if not SUPABASE_URL or not SUPABASE_KEY or "FILL_IN" in (SUPABASE_URL or ""):
        print("WARNING: Supabase credentials not set — skipping counselor note log")
        return None

    payload = {
        "school_name": school_name,
        "student_id_hash": student_id_hash,
        "note_text": note_text,
        "severity": severity,
        "staff_id": staff_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/counselor_notes",
            headers=_headers(),
            json=payload,
            timeout=10,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            record = data[0] if data else {}
            print(f"[counselor] Note logged for student {student_id_hash} at {school_name} (id: {record.get('id')})")
            return record
        print(f"[counselor] WARNING: Supabase returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[counselor] WARNING: Failed to log note: {e}")
    return None


def check_escalation_pattern(school_name: str, student_id_hash: str) -> dict:
    """
    Returns:
      {"escalate": bool, "tip_count": int, "note_count": int, "reason": str}

    Escalate = True when:
      (tip_count >= 2 AND note_count >= 1) OR note_count >= 3
    """
    if not SUPABASE_URL or not SUPABASE_KEY or "FILL_IN" in (SUPABASE_URL or ""):
        print("WARNING: Supabase credentials not set — skipping escalation check")
        return {"escalate": False, "tip_count": 0, "note_count": 0, "reason": "credentials_missing"}

    tip_count = 0
    note_count = 0

    # Count tips from same school
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/tips",
            headers={**_headers(), "Prefer": "count=exact"},
            params={"school_name": f"eq.{school_name}", "select": "id"},
            timeout=10,
        )
        if resp.status_code == 200:
            # Supabase returns count in Content-Range header
            content_range = resp.headers.get("Content-Range", "0-0/0")
            # e.g.  "0-4/5"  or  "*/5"
            try:
                tip_count = int(content_range.split("/")[-1])
            except (ValueError, IndexError):
                tip_count = len(resp.json())
    except Exception as e:
        print(f"[counselor] WARNING: Tip count query failed: {e}")

    # Count counselor notes for same student hash
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/counselor_notes",
            headers={**_headers(), "Prefer": "count=exact"},
            params={"student_id_hash": f"eq.{student_id_hash}", "select": "id"},
            timeout=10,
        )
        if resp.status_code == 200:
            content_range = resp.headers.get("Content-Range", "0-0/0")
            try:
                note_count = int(content_range.split("/")[-1])
            except (ValueError, IndexError):
                note_count = len(resp.json())
    except Exception as e:
        print(f"[counselor] WARNING: Note count query failed: {e}")

    if note_count >= 3:
        reason = f"{note_count} counselor notes on record for this student — sustained concern pattern"
        return {"escalate": True, "tip_count": tip_count, "note_count": note_count, "reason": reason}

    if tip_count >= 2 and note_count >= 1:
        reason = f"{tip_count} tips from {school_name} combined with {note_count} counselor note(s) for this student"
        return {"escalate": True, "tip_count": tip_count, "note_count": note_count, "reason": reason}

    return {
        "escalate": False,
        "tip_count": tip_count,
        "note_count": note_count,
        "reason": "below_threshold",
    }
