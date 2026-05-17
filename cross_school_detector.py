"""
Cross-school pattern detection.
Detects if multiple schools in the district received similar threat types recently.
Helps identify coordinated threat campaigns or copycat incidents across campuses.
"""
import os
from datetime import datetime, timedelta, timezone

import requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


def _headers() -> dict:
    return {
        "apikey": SUPABASE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_KEY or ''}",
        "Content-Type": "application/json",
    }


def detect_cross_school_pattern(school: str, threat_type: str, call_id: str) -> dict | None:
    """
    Query recent tips (last 7 days) for the same threat_type across different schools.

    Returns an alert dict if a cross-school pattern is found, None otherwise.

    Alert structure:
        {
            "alert": True,
            "message": str,
            "affected_schools": list[str],
            "threat_type": str,
            "window_days": 7,
        }
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        print(f"[{call_id}] WARNING: SUPABASE env vars not set — skipping cross-school detection")
        return None

    if not threat_type:
        return None

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        # Query tips table: same category, last 7 days, different school
        params = {
            "select": "school_name",
            "category": f"eq.{threat_type}",
            "submitted_at": f"gte.{cutoff}",
            "school_name": f"neq.{school}",
        }

        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/tips",
            headers=_headers(),
            params=params,
            timeout=10,
        )

        if r.status_code != 200:
            print(f"[{call_id}] WARNING: cross-school query returned {r.status_code}: {r.text[:100]}")
            return None

        rows = r.json()
        if not isinstance(rows, list):
            return None

        # Collect unique school names (excluding None/empty)
        affected: list[str] = []
        seen: set[str] = set()
        for row in rows:
            name = row.get("school_name")
            if name and name not in seen:
                seen.add(name)
                affected.append(name)

        count = len(affected)

        if count == 0:
            return None

        if count == 1:
            return {
                "alert": True,
                "urgency": "medium",
                "message": (
                    f"1 other school reported {threat_type} threats in the last 7 days "
                    f"({affected[0]}). Monitor for possible pattern."
                ),
                "affected_schools": affected,
                "threat_type": threat_type,
                "window_days": 7,
            }

        # 2 or more other schools — elevated alert
        school_list = ", ".join(affected[:5])  # cap display at 5
        if len(affected) > 5:
            school_list += f" (+{len(affected) - 5} more)"

        return {
            "alert": True,
            "urgency": "high",
            "message": (
                f"CROSS-SCHOOL PATTERN: {count} other schools reported {threat_type} threats "
                f"in the last 7 days. Possible coordinated event. "
                f"Affected schools: {school_list}."
            ),
            "affected_schools": affected,
            "threat_type": threat_type,
            "window_days": 7,
        }

    except Exception as e:
        print(f"[{call_id}] WARNING: cross-school detection failed: {e}")
        return None


def get_district_threat_summary(days: int = 30) -> list:
    """
    Return recent tips grouped by school for the dashboard API.

    Each entry: { school_name, tip_count, categories, latest_at, max_urgency }
    Returns an empty list if Supabase is not configured or the query fails.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("WARNING: SUPABASE env vars not set — returning empty district summary")
        return []

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/tips",
            headers=_headers(),
            params={
                "select": "school_name,category,urgency,submitted_at",
                "submitted_at": f"gte.{cutoff}",
                "order": "submitted_at.desc",
                "limit": "500",
            },
            timeout=10,
        )

        if r.status_code != 200:
            print(f"WARNING: district summary query returned {r.status_code}")
            return []

        rows = r.json()
        if not isinstance(rows, list):
            return []

        # Group by school_name
        school_map: dict[str, dict] = {}
        urgency_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        for row in rows:
            name = row.get("school_name") or "Unknown"
            if name not in school_map:
                school_map[name] = {
                    "school_name": name,
                    "tip_count": 0,
                    "categories": [],
                    "latest_at": None,
                    "max_urgency": "low",
                }
            entry = school_map[name]
            entry["tip_count"] += 1

            cat = row.get("category")
            if cat and cat not in entry["categories"]:
                entry["categories"].append(cat)

            ts = row.get("submitted_at")
            if ts and (entry["latest_at"] is None or ts > entry["latest_at"]):
                entry["latest_at"] = ts

            urg = (row.get("urgency") or "low").lower()
            if urgency_rank.get(urg, 0) > urgency_rank.get(entry["max_urgency"], 0):
                entry["max_urgency"] = urg

        # Sort by tip_count descending
        return sorted(school_map.values(), key=lambda x: x["tip_count"], reverse=True)

    except Exception as e:
        print(f"WARNING: get_district_threat_summary failed: {e}")
        return []
