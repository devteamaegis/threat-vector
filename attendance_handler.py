import os
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def log_attendance(data: dict, call_id: str):
    if not SUPABASE_URL or not SUPABASE_KEY:
        print(f"[{call_id}] WARNING: Supabase credentials not set — skipping attendance log")
        return None

    payload = {
        "call_id": call_id,
        "school_name": data.get("school_name"),
        "student_name": data.get("student_name"),
        "teacher_name": data.get("teacher_name"),
        "grade": data.get("grade"),
        "absence_date": data.get("absence_date"),
        "reason": data.get("reason"),
    }

    try:
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/attendance_logs",
            headers=_headers(),
            json=payload,
            timeout=10,
        )
        if response.status_code in (200, 201):
            result = response.json()
            attendance_id = result[0].get("id") if result else None
            print(f"[{call_id}] Attendance logged: {attendance_id}")
            return attendance_id
        print(f"[{call_id}] WARNING: Attendance log returned {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"[{call_id}] WARNING: Attendance log failed: {e}")
    return None
