#!/usr/bin/env python3
"""
Seed the Supabase `tips` table with 50 realistic historical threat records.

These are fully synthetic — no real schools, people, or incidents.
They exist to:
  1. Populate the 3D knowledge graph with clusters to show
  2. Give Supermemory prior memories to surface during demo calls
  3. Give Moss semantic context to match against
  4. Make the dashboard look like a real production system with history

Run once: python seed_database.py
"""

import os
import json
import random
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

SCHOOLS = [
    "Westbrook Academy",
    "Ridgecrest High School",
    "Maplewood Middle School",
    "Northgate High School",
    "Cedarwood Elementary",
    "Lakeside Academy",
    "Greenfield High School",
    "Pinecrest Middle School",
    "Stonehaven Academy",
    "Crestview High School",
]

RECORDS = [
    # ── Weapon threats (level 4-5) ─────────────────────────────────────────
    {
        "school": "Westbrook Academy", "category": "weapon", "urgency": "critical",
        "description": "Caller reports a student showed classmates a photo of a handgun on his phone during lunch and said 'I'll show them what happens.' Multiple witnesses. Student is a junior, known for volatile behavior.",
        "summary": "Credible weapon threat at Westbrook Academy. Student showing weapon photos with explicit threatening statement. Multiple witnesses corroborate. Immediate response warranted.",
        "level": 5, "action": "immediate_911", "emotion": "distressed", "tone": "urgent",
        "escalation": "imminent", "timeline": "today",
        "credibility": ["Multiple witnesses corroborated", "Photo evidence described", "Explicit verbal threat"],
        "facts": ["Student showed handgun photo", "Said 'I'll show them'", "3 witnesses confirmed", "Junior student", "History of volatile behavior"],
        "days_ago": 45,
    },
    {
        "school": "Ridgecrest High School", "category": "weapon", "urgency": "critical",
        "description": "Anonymous tip that a backpack in locker 247 contains a knife. Caller says they saw the student pull it out in the bathroom and threaten another student. Incident happened this morning.",
        "summary": "Knife in locker 247 at Ridgecrest High. Witness reports direct threat against another student in bathroom this morning.",
        "level": 5, "action": "immediate_911", "emotion": "panicked", "tone": "urgent",
        "escalation": "imminent", "timeline": "today",
        "credibility": ["Direct witness", "Specific locker number", "Morning incident"],
        "facts": ["Knife in locker 247", "Threat made in bathroom", "Direct witness", "This morning"],
        "days_ago": 12,
    },
    {
        "school": "Northgate High School", "category": "weapon", "urgency": "high",
        "description": "Student overheard in the parking lot saying he brought 'something' to school and is going to use it at the pep rally on Friday. Caller is a teacher's aide.",
        "summary": "Potential weapon threat targeting Friday pep rally at Northgate High. Staff member witness.",
        "level": 4, "action": "notify_principal", "emotion": "anxious", "tone": "matter_of_fact",
        "escalation": "escalating", "timeline": "this_week",
        "credibility": ["Staff witness (teacher's aide)", "Specific event targeted", "Heard directly"],
        "facts": ["Said 'brought something'", "Targeting Friday pep rally", "Overheard in parking lot", "Staff witness"],
        "days_ago": 8,
    },
    {
        "school": "Greenfield High School", "category": "weapon", "urgency": "critical",
        "description": "Parent calling. Child came home and said a classmate has been showing students pictures of multiple guns and ammunition, and has a list of student names. This has been going on for two weeks.",
        "summary": "Escalating pattern at Greenfield High — student displaying weapon photos and maintaining a target list for 2+ weeks. High credibility, parent source.",
        "level": 5, "action": "immediate_911", "emotion": "distressed", "tone": "urgent",
        "escalation": "imminent", "timeline": "this_week",
        "credibility": ["Parent witness via child", "Two-week pattern", "Target list mentioned"],
        "facts": ["Multiple gun photos", "Ammunition shown", "2-week pattern", "Names list maintained"],
        "days_ago": 3,
    },

    # ── Bullying (level 2-3) ───────────────────────────────────────────────
    {
        "school": "Maplewood Middle School", "category": "bullying", "urgency": "medium",
        "description": "Student being systematically excluded and harassed by a group. Caller says victim has been coming home crying every day for three weeks. Physical intimidation in hallways.",
        "summary": "Sustained group bullying at Maplewood. Physical component. Three-week pattern affecting student's daily functioning.",
        "level": 3, "action": "notify_principal", "emotion": "calm", "tone": "matter_of_fact",
        "escalation": "escalating", "timeline": "this_week",
        "credibility": ["Parent direct observation", "Three-week documented pattern"],
        "facts": ["Daily harassment", "Physical intimidation", "Group of students", "3-week duration", "Victim visibly distressed"],
        "days_ago": 30,
    },
    {
        "school": "Cedarwood Elementary", "category": "bullying", "urgency": "medium",
        "description": "Third-grade student being called slurs related to his race by a group of students. Parent says it's happening daily on the playground and the teacher is not intervening.",
        "summary": "Racial harassment at Cedarwood Elementary. Daily incidents on playground. Teacher inaction reported.",
        "level": 3, "action": "notify_principal", "emotion": "distressed", "tone": "emotional",
        "escalation": "escalating", "timeline": "this_week",
        "credibility": ["Parent direct report", "Daily recurrence", "Specific location"],
        "facts": ["Racial slurs", "Third grade", "Playground location", "Daily occurrence", "Teacher inaction"],
        "days_ago": 22,
    },

    # ── Self-harm / mental health (level 3-4) ────────────────────────────────
    {
        "school": "Stonehaven Academy", "category": "self_harm", "urgency": "high",
        "description": "Caller is a friend of a student who showed them a note she wrote saying she wants to end her life. The note is dated for this weekend. Student has been giving away personal items.",
        "summary": "Credible suicide risk at Stonehaven Academy. Written note with specific timeline. Pre-suicidal behavior (giving away possessions). Immediate intervention required.",
        "level": 4, "action": "notify_principal", "emotion": "panicked", "tone": "urgent",
        "escalation": "imminent", "timeline": "this_week",
        "credibility": ["Note seen directly", "Specific date", "Behavioral changes observed"],
        "facts": ["Written suicide note", "Weekend timeline", "Giving away items", "Peer directly witnessed"],
        "days_ago": 60,
    },
    {
        "school": "Lakeside Academy", "category": "self_harm", "urgency": "medium",
        "description": "Student has been cutting herself on her arms. A classmate noticed during PE class. Student told classmate she's been doing it for months and asked her not to tell anyone.",
        "summary": "Ongoing self-harm behavior at Lakeside Academy. Student asked peer for silence, indicating shame. Months-long duration.",
        "level": 3, "action": "notify_principal", "emotion": "anxious", "tone": "guarded",
        "escalation": "stable", "timeline": "unknown",
        "credibility": ["Direct witness during PE", "Student self-disclosed"],
        "facts": ["Visible cuts on arms", "Months-long pattern", "PE class discovery", "Student self-disclosed to peer"],
        "days_ago": 90,
    },

    # ── Threats (level 3-5) ──────────────────────────────────────────────────
    {
        "school": "Westbrook Academy", "category": "threat", "urgency": "critical",
        "description": "Anonymous caller says a student posted a video on social media threatening to 'shoot up' the school gym during tonight's basketball game. The post has been shared widely.",
        "summary": "Social media threat targeting tonight's game at Westbrook Academy. Widely circulated, time-critical.",
        "level": 5, "action": "immediate_911", "emotion": "anxious", "tone": "urgent",
        "escalation": "imminent", "timeline": "today",
        "credibility": ["Social media evidence", "Specific event targeted", "Wide circulation confirms"],
        "facts": ["Social media video threat", "Targets basketball game tonight", "Gym specified", "Widely shared"],
        "days_ago": 35,
    },
    {
        "school": "Ridgecrest High School", "category": "threat", "urgency": "high",
        "description": "A student received a direct message threatening their life. The message said 'I know where you live and I will get you after school.' Caller is the victim's parent.",
        "summary": "Direct death threat via DM at Ridgecrest. Specific after-school timeline. Parent reporting on behalf of victim.",
        "level": 4, "action": "notify_principal", "emotion": "distressed", "tone": "urgent",
        "escalation": "imminent", "timeline": "today",
        "credibility": ["Screenshot evidence (parent)", "Specific threat language", "Specific timeline"],
        "facts": ["Direct message death threat", "After-school timing", "Home address implied", "Screenshot exists"],
        "days_ago": 18,
    },
    {
        "school": "Northgate High School", "category": "threat", "urgency": "medium",
        "description": "A group of students overheard a classmate say if he failed his finals he would 'burn this school to the ground.' Finals are next week.",
        "summary": "Low-specificity threat at Northgate. Conditional on academic outcome. Multiple witnesses. Finals timeline.",
        "level": 3, "action": "monitor", "emotion": "calm", "tone": "casual",
        "escalation": "stable", "timeline": "this_week",
        "credibility": ["Multiple student witnesses", "Specific trigger condition", "Specific timeline"],
        "facts": ["Arson threat", "Conditional on failing finals", "Multiple witnesses", "Finals next week"],
        "days_ago": 14,
    },

    # ── Drugs (level 2-3) ────────────────────────────────────────────────────
    {
        "school": "Crestview High School", "category": "drugs", "urgency": "medium",
        "description": "Student selling pills in the bathrooms. Caller says they've seen it happen three times this week. Pills are being sold between 3rd and 4th period.",
        "summary": "Active drug sales at Crestview High. Three confirmed incidents this week. Specific timing identified.",
        "level": 3, "action": "notify_principal", "emotion": "calm", "tone": "matter_of_fact",
        "escalation": "stable", "timeline": "today",
        "credibility": ["Three direct observations", "Specific timing pattern"],
        "facts": ["Pill sales in bathrooms", "3x this week", "Between 3rd-4th period", "Caller direct witness"],
        "days_ago": 25,
    },
    {
        "school": "Pinecrest Middle School", "category": "drugs", "urgency": "low",
        "description": "Caller smelled marijuana near the bleachers during last week's game. Thinks it was coming from a group of high schoolers who snuck in.",
        "summary": "Marijuana use near bleachers at Pinecrest. Low urgency, prior incident.",
        "level": 2, "action": "document", "emotion": "calm", "tone": "casual",
        "escalation": "stable", "timeline": "unknown",
        "credibility": ["Olfactory evidence", "Vague identification"],
        "facts": ["Marijuana smell", "Bleacher area", "Game night", "High school aged individuals"],
        "days_ago": 40,
    },

    # ── Harassment (level 2-3) ───────────────────────────────────────────────
    {
        "school": "Maplewood Middle School", "category": "harassment", "urgency": "medium",
        "description": "A teacher is reportedly sending inappropriate messages to a student. The student's parent found messages on their child's phone. The messages are personal in nature and happening outside school hours.",
        "summary": "Potential staff-student boundary violation at Maplewood. Parent has message evidence. Requires immediate administrative review.",
        "level": 4, "action": "notify_principal", "emotion": "distressed", "tone": "guarded",
        "escalation": "escalating", "timeline": "today",
        "credibility": ["Parent has evidence (messages)", "Outside school hours pattern"],
        "facts": ["Teacher sending personal messages", "Student targeted", "After-hours contact", "Parent has screenshots"],
        "days_ago": 7,
    },
    {
        "school": "Greenfield High School", "category": "harassment", "urgency": "medium",
        "description": "Female student receiving unsolicited explicit photos from a male classmate via social media. It has happened four times. Student is afraid to come to school.",
        "summary": "Cyber sexual harassment at Greenfield High. Four incidents, school avoidance behavior. Title IX implications.",
        "level": 3, "action": "notify_principal", "emotion": "distressed", "tone": "emotional",
        "escalation": "escalating", "timeline": "this_week",
        "credibility": ["Parent reporting with evidence", "Four documented incidents", "Behavioral impact"],
        "facts": ["Unsolicited explicit images", "4x incidents", "Social media platform", "School avoidance"],
        "days_ago": 20,
    },

    # ── Vandalism (level 1-2) ────────────────────────────────────────────────
    {
        "school": "Cedarwood Elementary", "category": "vandalism", "urgency": "low",
        "description": "Graffiti was spray-painted on the gym wall over the weekend. It includes a racial slur. A parent photographed it this morning.",
        "summary": "Racially charged vandalism at Cedarwood. Photographic evidence. Weekend incident discovered Monday morning.",
        "level": 2, "action": "notify_principal", "emotion": "calm", "tone": "matter_of_fact",
        "escalation": "stable", "timeline": "today",
        "credibility": ["Photo evidence", "Physical evidence on-site"],
        "facts": ["Spray paint graffiti", "Racial slur content", "Gym wall", "Weekend occurrence", "Photo taken"],
        "days_ago": 50,
    },

    # ── Additional Westbrook records (for clustering demo) ───────────────────
    {
        "school": "Westbrook Academy", "category": "threat", "urgency": "high",
        "description": "Student overheard making comments about 'making a list' and researching the school's security camera locations online. Two students reported this independently.",
        "summary": "Pre-attack planning behavior at Westbrook Academy. Camera surveillance research concerning. Two independent reports.",
        "level": 4, "action": "notify_principal", "emotion": "calm", "tone": "matter_of_fact",
        "escalation": "escalating", "timeline": "unknown",
        "credibility": ["Two independent reports", "Specific research behavior", "Planning indicators"],
        "facts": ["'Making a list' comment", "Camera location research", "Two independent witnesses", "Planning behavior pattern"],
        "days_ago": 20,
    },
    {
        "school": "Westbrook Academy", "category": "weapon", "urgency": "high",
        "description": "A student told their parent they saw a classmate with what appeared to be a stun gun or taser in their locker room bag. The student is a sophomore and has been suspended before.",
        "summary": "Possible stun gun at Westbrook Academy. Locker room location. Prior disciplinary history on the subject.",
        "level": 4, "action": "notify_principal", "emotion": "anxious", "tone": "guarded",
        "escalation": "stable", "timeline": "today",
        "credibility": ["Direct witness (student)", "Specific location (locker room)", "Prior history on subject"],
        "facts": ["Stun gun/taser sighting", "Locker room location", "Sophomore student", "Prior suspensions"],
        "days_ago": 10,
    },
]

# Pad to 50 with auto-generated low-level records
ADDITIONAL_PATTERNS = [
    ("bullying",    "low",    "Caller reports ongoing verbal bullying in {school} cafeteria. Requesting counselor intervention.",        1, "document"),
    ("drugs",       "low",    "Anonymous report of possible marijuana use in {school} parking lot after school hours.",                   1, "document"),
    ("vandalism",   "low",    "Graffiti found on bathroom wall at {school}. No threatening content. Maintenance notified.",               1, "document"),
    ("harassment",  "medium", "Student reports being followed home from {school} by an unknown adult. No direct threats made.",           3, "monitor"),
    ("threat",      "medium", "Caller reports a social media post making vague threats about {school}. Post has been screenshotted.",     3, "monitor"),
    ("self_harm",   "medium", "Counselor tip: student at {school} expressing feelings of hopelessness in journal found by parent.",       3, "notify_principal"),
    ("weapon",      "high",   "Report of a student at {school} bragging about having a knife. No witnesses beyond the caller.",           3, "notify_principal"),
    ("bullying",    "high",   "Group of students at {school} threatening a student with physical harm if they tell anyone about assault.", 4, "notify_principal"),
]

def generate_additional(n: int = 31) -> list[dict]:
    """Generate additional low-to-mid level records to reach 50 total."""
    records = []
    for i in range(n):
        pattern = ADDITIONAL_PATTERNS[i % len(ADDITIONAL_PATTERNS)]
        cat, urgency, desc_tmpl, level, action = pattern
        school = random.choice(SCHOOLS)
        records.append({
            "school": school,
            "category": cat,
            "urgency": urgency,
            "description": desc_tmpl.format(school=school),
            "summary": f"{cat.replace('_',' ').title()} report at {school}. Under review.",
            "level": level,
            "action": action,
            "emotion": random.choice(["calm", "anxious"]),
            "tone": random.choice(["matter_of_fact", "casual", "guarded"]),
            "escalation": random.choice(["stable", "stable", "escalating"]),
            "timeline": random.choice(["today", "this_week", "unknown"]),
            "credibility": ["Anonymous caller"],
            "facts": [desc_tmpl.format(school=school)[:80]],
            "days_ago": random.randint(1, 120),
        })
    return records


def build_supabase_row(r: dict, idx: int) -> dict:
    ts = (datetime.now(datetime.timezone.utc if hasattr(datetime, 'timezone') else None) - timedelta(days=r["days_ago"], hours=random.randint(0,12))).isoformat()
    from datetime import timezone
    ts = (datetime.now(timezone.utc) - timedelta(days=r["days_ago"], hours=random.randint(0,12))).isoformat()

    base = {
        "description": r["description"],
        "category": r["category"],
        "urgency": r["urgency"],
        "severity": r["urgency"],
        "status": random.choice(["resolved", "resolved", "reviewed", "new"]),
        "is_anonymous": True,
        "ai_summary": r["summary"],
        "ai_triage_score": r["level"] * 2,
        "ai_recommended_action": r["action"],
        "school_name": r["school"],
        "created_at": ts,
        "submitted_at": ts,
    }
    # Extended columns — added by migration.sql
    extended = {
        "caller_emotion": r["emotion"],
        "caller_tone": r["tone"],
        "escalation_risk": r["escalation"],
        "timeline": r["timeline"],
        "credibility_signals": json.dumps(r["credibility"]),
        "key_facts": json.dumps(r["facts"]),
        "call_duration_seconds": random.randint(18, 120),
    }
    return {**base, **extended}


def seed():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        return

    all_records = RECORDS + generate_additional(50 - len(RECORDS))
    rows = [build_supabase_row(r, i) for i, r in enumerate(all_records)]

    url = f"{SUPABASE_URL}/rest/v1/tips"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    # Insert in batches of 10
    inserted = 0
    for i in range(0, len(rows), 10):
        batch = rows[i:i+10]
        r = requests.post(url, headers=headers, json=batch, timeout=15)
        if r.status_code in (200, 201):
            inserted += len(batch)
            print(f"  Inserted batch {i//10 + 1}: {len(batch)} records")
        else:
            print(f"  ERROR batch {i//10 + 1}: {r.status_code} — {r.text[:200]}")

    print(f"\n✓ Seeded {inserted} historical threat records into Supabase.")
    print(f"  Schools: {len(set(r['school'] for r in all_records))}")
    print(f"  Categories: {set(r['category'] for r in all_records)}")
    print(f"  Date range: {max(r['days_ago'] for r in all_records)} days back")


if __name__ == "__main__":
    seed()
