import os
import requests
from datetime import datetime, timezone, timedelta

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def check_attendance_anomaly(school_name: str, call_id: str) -> dict:
    """
    Checks whether there is an attendance anomaly correlated with a known tip.

    Returns:
      {"anomaly": True, "absence_count": int, "related_tip_id": str, "message": str}
      OR
      {"anomaly": False}
    """
    if not SUPABASE_URL or not SUPABASE_KEY or "FILL_IN" in (SUPABASE_URL or ""):
        print(f"[{call_id}] WARNING: Supabase credentials not set — skipping attendance anomaly check")
        return {"anomaly": False}

    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    fourteen_days_ago = (now - timedelta(days=14)).isoformat()

    # Count absences from this school in the past 7 days
    absence_count = 0
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/attendance_logs",
            headers={**_headers(), "Prefer": "count=exact"},
            params={
                "school_name": f"eq.{school_name}",
                "absence_date": f"gte.{seven_days_ago}",
                "select": "id",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            content_range = resp.headers.get("Content-Range", "0-0/0")
            try:
                absence_count = int(content_range.split("/")[-1])
            except (ValueError, IndexError):
                absence_count = len(resp.json())
    except Exception as e:
        print(f"[{call_id}] WARNING: Attendance query failed: {e}")
        return {"anomaly": False}

    if absence_count < 3:
        return {"anomaly": False}

    # Look for a related critical/high tip from the same school in the past 14 days
    related_tip_id = None
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/tips",
            headers=_headers(),
            params={
                "school_name": f"eq.{school_name}",
                "urgency": "in.(critical,high)",
                "created_at": f"gte.{fourteen_days_ago}",
                "select": "id",
                "limit": 1,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                related_tip_id = data[0].get("id")
    except Exception as e:
        print(f"[{call_id}] WARNING: Related tip query failed: {e}")

    if related_tip_id is None:
        return {"anomaly": False}

    message = (
        f"ATTENDANCE ANOMALY: {absence_count} absences at {school_name} in the past 7 days "
        f"correlated with a high/critical tip (id: {related_tip_id[:8]}). "
        "Possible fear-driven avoidance pattern."
    )
    return {
        "anomaly": True,
        "absence_count": absence_count,
        "related_tip_id": related_tip_id,
        "message": message,
    }
