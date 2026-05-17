#!/usr/bin/env python3
"""
Large historical threat database seeder.
Based on real patterns from:
  - FBI Active Shooter Incident Reports (2000–2023)
  - K-12 School Shooting Database (CHDS, David Riedman)
  - Secret Service NTAC School Safety Reports
  - ALERRT behavioral threat assessment data

Generates 200 synthetic tip records modeled on real threat categories,
language patterns, and school demographics across the US.

Usage: python seed_large.py
"""
import os, json, random, requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

# ── Real school names across US regions ────────────────────────────────────────
SCHOOLS = [
    # Northeast
    "Westbrook Academy", "Lincoln High School", "Jefferson Middle School",
    "Riverside Preparatory", "Northgate High School", "Eastside Academy",
    # Southeast
    "Palmview High School", "Magnolia Ridge Academy", "Suncoast Middle School",
    "Cypress Creek High", "Heritage Academy", "Lakewood High School",
    # Midwest
    "Prairie View High School", "Oakdale Academy", "Riverdale High School",
    "Centennial Middle School", "Pinecrest Academy", "Crossroads High School",
    # Southwest
    "Desert Ridge Academy", "Cactus Valley High School", "Mesa View Middle",
    "Sunridge High School", "Canyon View Academy", "Horizon High School",
    # West
    "Pacific Crest High School", "Sierra View Academy", "Redwood High School",
    "Coastline Middle School", "Golden Gate Academy", "Valley View High School",
]

# ── Transcripts modeled on real FBI behavioral indicators ─────────────────────
# Each tuple: (threat_type, urgency, level, transcript, summary, location, subject, timeline, emotion, action)

TRANSCRIPT_TEMPLATES = [
    # ── WEAPON THREATS (Level 4-5) ──────────────────────────────────────────
    (
        "weapon", "critical", 5,
        "I need to report something serious. My friend Jake — he goes to {school} — he showed me a gun this morning before school. He said he was going to bring it in on Friday and 'make them all pay' because he got suspended last week. He showed me the actual gun, it was in his backpack. He's been getting worse, talking about this for weeks. I'm really scared. Please you have to do something.",
        "Caller reports a named student showed a firearm before school and made explicit threats to return Friday. Student has prior suspension, escalating behavior over weeks.",
        "Main entrance / front hallway", "Male student, 10th grade, Jake, approximately 16", "Friday — imminent",
        "panicked", "immediate_lockdown"
    ),
    (
        "weapon", "critical", 5,
        "There's a kid at {school} who's been posting stuff online about shooting the school. I saw his posts last night, he was talking about a specific date — next Wednesday. He mentioned the gym specifically. He said he has access to his dad's rifles. His name is Tyler and he's in 11th grade. He sits alone at lunch, nobody talks to him. This feels real.",
        "Online threat posts naming specific date (next Wednesday), location (gym), and weapon access. Subject identified by first name, 11th grade.",
        "Gymnasium", "Male, 11th grade, Tyler, sits alone at lunch", "Next Wednesday",
        "fearful", "immediate_lockdown"
    ),
    (
        "weapon", "critical", 5,
        "My son goes to {school} and he told me tonight that one of the kids in his class has been telling everyone he has a knife and is going to stab his ex-girlfriend. The girl's name is Marisol and she's in 9th grade. The boy has been threatening her for two weeks since she broke up with him. Today he followed her home. I'm terrified.",
        "Parent reports student making repeated stabbing threats against named ex-girlfriend over two weeks, including following victim home today.",
        "Campus-wide, victim in 9th grade", "Male student, escalating stalking behavior toward ex-girlfriend Marisol", "Ongoing — today",
        "distressed", "immediate_lockdown"
    ),
    (
        "weapon", "high", 4,
        "I overheard two boys talking in the bathroom at {school} today. One of them said he was going to 'take care of things' after the game on Friday and he mentioned something in his car. The other one was telling him to calm down. I don't know their names but one of them was wearing a red Northface jacket. This felt serious.",
        "Caller overheard threatening statement in restroom referencing 'after the game Friday' and a vehicle. Partial description of subject.",
        "Men's restroom, main building", "Male student, red Northface jacket, no further ID", "Friday after the game",
        "anxious", "investigate"
    ),
    (
        "weapon", "high", 4,
        "Someone sent a group chat screenshot to me showing a student at {school} saying he was going to shoot up the school. The message was sent last night at like 11pm. It's a real student — I know him, his name is Devon. He's been in fights before. The screenshot is real, I can send it somewhere.",
        "Screenshotted online threat from identified student (Devon) posted previous night. Caller can provide evidence.",
        "Unknown", "Male student, Devon, history of fights on campus", "Unclear — threat posted last night",
        "anxious", "investigate"
    ),

    # ── BULLYING / HARASSMENT (Level 2-3) ────────────────────────────────────
    (
        "bullying", "medium", 3,
        "There's a group of kids at {school} that's been targeting my daughter for months. It's gotten to the point where she doesn't want to go to school. Last week they cornered her in the bathroom and pushed her. There are about five girls involved. My daughter is in 8th grade. I've told the school counselor twice and nothing happened.",
        "Ongoing group bullying targeting 8th grade female student, escalating to physical assault in restroom. Prior school reports unaddressed.",
        "Girls' bathroom, main building", "Group of approximately 5 female students, 8th grade", "Ongoing, months",
        "distressed", "counselor_intervention"
    ),
    (
        "bullying", "medium", 3,
        "A kid at {school} has been sending death threats to my son over Snapchat. He screenshots everything. They've been saying they're going to jump him after school on Thursday. There's about three of them and they've done it before to another kid. My son is scared to go to school.",
        "Death threats via Snapchat from group of 3 students, with planned attack after school Thursday. Prior incidents with another victim.",
        "Off-campus threat, after school vicinity", "Group of 3 male students, specific threat for Thursday afternoon", "Thursday after school",
        "distressed", "investigate"
    ),
    (
        "bullying", "low", 2,
        "I want to report some bullying happening at {school}. There's a kid in my class who gets made fun of every day in the cafeteria. Today it got physical — someone knocked his lunch tray. I feel bad for him. He's been crying in class. I don't know if this is serious enough to report but it seemed wrong.",
        "Witness reports daily cafeteria bullying of a student, escalating to physical contact. Victim showing emotional distress.",
        "Cafeteria", "Male student, victim, no further details", "Ongoing daily",
        "calm", "counselor_intervention"
    ),

    # ── SELF-HARM / MENTAL HEALTH (Level 3) ──────────────────────────────────
    (
        "self_harm", "high", 4,
        "I'm really worried about my best friend at {school}. She told me today that she doesn't want to be alive anymore and she has a plan. She said she has pills at home. She's been really depressed since her parents split up. I don't know what to do. She made me promise not to tell anyone but I can't just do nothing. Please help her.",
        "Immediate suicide risk: student has stated plan involving pills. Known precipitating factor (family situation). High credibility — close friend reporting.",
        "Off-campus / student's home", "Female student, 9th or 10th grade, depressive episode", "Today — immediate",
        "fearful", "crisis_intervention"
    ),
    (
        "self_harm", "medium", 3,
        "A student at {school} has been posting really dark things on Instagram. Talking about not seeing the point anymore, saying goodbye to people. I don't know if it's for attention but it felt real. She hasn't been in school for three days. Her username is visible if you need it.",
        "Student posting concerning farewell-type content on social media, absent from school 3 days. Caller can provide account details.",
        "Off-campus / social media", "Female student, specific Instagram account available", "Last 3 days, escalating",
        "anxious", "welfare_check"
    ),
    (
        "self_harm", "medium", 3,
        "One of the boys in my son's friend group has been cutting himself. My son showed me his arms when he saw them in PE class yesterday. The kid told him he's been doing it for a month. He says his home life is really bad. He doesn't want anyone to know. My son is scared for him.",
        "Non-suicidal self-injury identified by peer, ongoing for a month. Student confided to friend, subject's home situation reportedly difficult.",
        "PE class / locker room", "Male student, friend group, specific student known to reporter's son", "Last month, ongoing",
        "calm", "counselor_intervention"
    ),

    # ── DRUG / SUBSTANCE (Level 2) ────────────────────────────────────────────
    (
        "drugs", "medium", 3,
        "There's a kid at {school} who's been selling pills in the parking lot before first period. I've seen it happen three times this week. He drives a white Honda Civic and parks near the back entrance. The pills look like they could be Xanax or something. Multiple students are buying from him.",
        "Repeated drug sales in school parking lot before school, white Honda Civic, multiple buyers. Possible prescription pills.",
        "Back parking lot, near rear entrance", "Male student with white Honda Civic, seller", "This week, recurring mornings",
        "calm", "law_enforcement"
    ),
    (
        "drugs", "low", 2,
        "I think some kids at {school} are smoking weed in the bathroom by the gym. I could smell it when I walked by and I heard laughing. This has been happening for at least two weeks.",
        "Suspected marijuana use in gym-area restroom, ongoing two weeks.",
        "Bathroom near gymnasium", "Unknown students, multiple", "Ongoing, last 2 weeks",
        "calm", "administrative_action"
    ),
    (
        "drugs", "high", 4,
        "My daughter's friend overdosed at a party last weekend and she told me kids at {school} have been getting fentanyl pills from someone at the school. She said one of the 12th graders is the one bringing it in. This is serious — someone almost died. I'm scared for all these kids.",
        "Fentanyl distribution within school population, near-fatal overdose of a student at recent party. Source identified as 12th grade student.",
        "Unknown — distribution throughout school", "Male 12th grade student, described as dealer", "Active — ongoing distribution",
        "distressed", "law_enforcement"
    ),

    # ── HARASSMENT / THREATS (Level 2-3) ─────────────────────────────────────
    (
        "harassment", "medium", 3,
        "A teacher at {school} has been making really inappropriate comments to students. Multiple girls in my class have noticed it. He makes comments about our clothes and asks personal questions. One girl cried after his class last week. We're all uncomfortable but scared to say anything. I don't want to get in trouble.",
        "Multiple students uncomfortable with teacher making inappropriate comments about appearance and asking personal questions. One student visibly distressed.",
        "Classroom, specific teacher", "Teacher, male, multiple student victims in one class", "Ongoing",
        "anxious", "administrative_action"
    ),
    (
        "harassment", "medium", 3,
        "Someone has been leaving threatening notes in a girl's locker at {school}. The notes say things like 'you're going to regret this' and 'I know where you live.' This has been going on for three weeks. The girl is really scared. She doesn't know who it is.",
        "Anonymous threatening notes placed in student's locker for three weeks, including knowledge of home address. Victim experiencing ongoing fear.",
        "Student locker, main hallway", "Unknown perpetrator, female victim", "Three weeks, ongoing",
        "anxious", "investigate"
    ),
    (
        "harassment", "low", 2,
        "There's been a lot of racist graffiti appearing in the bathrooms at {school}. It's been there for two weeks and nobody seems to be doing anything about it. It's targeting Black students specifically. It makes me feel unsafe. Other students have seen it too.",
        "Racist graffiti targeting Black students in school bathrooms, present for two weeks, reportedly unaddressed by school.",
        "Multiple bathrooms", "Unknown, targeting students by race", "Two weeks, ongoing",
        "calm", "administrative_action"
    ),

    # ── GENERAL THREAT (Level 2-4) ────────────────────────────────────────────
    (
        "threat", "high", 4,
        "I heard from multiple people that there's going to be a fight at {school} tomorrow at lunch. Not just a regular fight — someone said one of the kids is going to bring a weapon. It's between two friend groups. A lot of kids know about it. I don't know exact names but I know it's real.",
        "Widely known planned fight at lunch tomorrow with reported weapon involvement between two student groups.",
        "Cafeteria / lunch area", "Two student groups, one reportedly armed", "Tomorrow at lunch",
        "anxious", "investigate"
    ),
    (
        "threat", "medium", 3,
        "Someone at {school} has been making bomb threat jokes in class. Today he said something like 'this place deserves to blow up' and everyone laughed but it didn't feel like a joke. He's been saying stuff like this for a month. The teacher didn't do anything. His name is Marcus.",
        "Student (Marcus) making repeated threatening statements about destroying school over one month. Teacher did not respond.",
        "Classroom", "Male student, Marcus, repeat threatening statements", "Month-long pattern, today",
        "uncertain", "investigate"
    ),
    (
        "threat", "critical", 5,
        "There's a note that was left on the ground by the cafeteria at {school} that says 'everyone at this school is going to die on Monday.' I picked it up and read it. The handwriting looks like a student. I didn't tell a teacher because I didn't know what to do but I kept the note. This was today.",
        "Physical written threat note found in cafeteria stating mass casualty threat for Monday. Note retained by caller.",
        "Cafeteria floor", "Unknown, handwritten note", "Monday — 3 days",
        "fearful", "immediate_lockdown"
    ),
    (
        "vandalism", "low", 1,
        "Someone broke the windows in the art room at {school} over the weekend. I saw it this morning when I walked by. Glass is everywhere. Doesn't look like an accident — all four windows are broken.",
        "Deliberate vandalism, four windows broken in art room over weekend.",
        "Art room, east wing", "Unknown", "Over the weekend",
        "calm", "administrative_action"
    ),
]

URGENCY_MAP = {
    "critical": "critical", "high": "high", "medium": "medium", "low": "low"
}

def random_date(days_back: int) -> str:
    offset = random.randint(0, days_back * 24 * 60)
    dt = datetime.utcnow() - timedelta(minutes=offset)
    return dt.isoformat() + "Z"

def build_record(template: tuple, school: str, idx: int) -> dict:
    (cat, urgency, level, transcript_tpl, summary, location, subject, timeline, emotion, action) = template

    transcript = transcript_tpl.replace("{school}", school)
    severity_map = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}

    bayes_map = {5: (85, 75, 95), 4: (55, 42, 68), 3: (22, 14, 31), 2: (8, 4, 13), 1: (2, 1, 4)}
    bayes_pct, ci_low, ci_high = bayes_map[level]
    bayes_pct += random.randint(-5, 5)
    bayes_pct = max(1, min(99, bayes_pct))

    gemini_level = level + random.choice([-1, 0, 0, 0, 1])
    gemini_level = max(1, min(5, gemini_level))
    consensus = abs(gemini_level - level) <= 1

    status_choices = ["new", "new", "new", "reviewing", "resolved"]
    # More recent = more likely new
    status = "new" if idx < 40 else random.choice(status_choices)

    return {
        "description": transcript,
        "category": cat,
        "urgency": urgency,
        "severity": severity_map[urgency],
        "status": status,
        "is_anonymous": True,
        "school_name": school,
        "ai_summary": summary,
        "ai_triage_score": level * 2,
        "ai_recommended_action": action,
        "caller_emotion": emotion,
        "caller_tone": "urgent" if level >= 4 else ("worried" if level == 3 else "calm"),
        "escalation_risk": "imminent" if level == 5 else ("escalating" if level >= 3 else "stable"),
        "location_detail": location,
        "subject_description": subject,
        "timeline": timeline,
        "gemini_level": gemini_level,
        "gemini_reasoning": f"Assessment based on specificity of threat, behavioral indicators, and timeline urgency. Level {gemini_level}/5.",
        "consensus": consensus,
        "three_model_consensus": consensus,
        "bayes_probability_pct": bayes_pct,
        "bayes_ci_low_pct": ci_low,
        "bayes_ci_high_pct": ci_high,
        "bayes_top_drivers": json.dumps([
            {"feature": "weapon_explicit", "keyword": "gun", "ratio": 12.0},
            {"feature": "timeline_immediate", "keyword": "today", "ratio": 8.0},
            {"feature": "specific_person", "keyword": "his name", "ratio": 5.0},
        ] if level >= 4 else [
            {"feature": "caller_fearful", "keyword": "scared", "ratio": 3.0},
            {"feature": "escalation_pattern", "keyword": "been doing", "ratio": 4.5},
        ]),
        "bayes_features_hit": json.dumps(["caller_fearful", "specific_person", "timeline_near"] if level >= 3 else ["caller_vague"]),
        "credibility_signals": json.dumps([
            "First-hand witness account",
            "Specific names, locations, and dates provided",
            "Consistent timeline detail",
        ] if level >= 4 else [
            "Second-hand report",
            "Some specificity in location",
        ]),
        "key_facts": json.dumps([
            f"School: {school}",
            f"Location: {location}",
            f"Timeline: {timeline}",
            f"Subject: {subject}",
        ]),
        "multilingual_call": False,
        "caller_language": "en",
        "submitted_at": random_date(90),
        "call_duration_seconds": random.randint(45, 280),
        "deepgram_confidence": round(random.uniform(0.87, 0.99), 2),
    }


def seed(batch_size: int = 20):
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        return

    print("Building 200 threat records from FBI/CHDS/ALERRT behavioral patterns...")
    records = []
    idx = 0
    # Cycle through all templates × schools to get 200+ records
    while len(records) < 200:
        template = TRANSCRIPT_TEMPLATES[idx % len(TRANSCRIPT_TEMPLATES)]
        school = random.choice(SCHOOLS)
        records.append(build_record(template, school, len(records)))
        idx += 1

    # Sort by submitted_at descending (newest first)
    records.sort(key=lambda r: r["submitted_at"], reverse=True)

    print(f"Inserting {len(records)} records in batches of {batch_size}...")
    success = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/tips",
            headers={**headers(), "Prefer": "return=minimal"},
            json=batch,
            timeout=20,
        )
        if r.status_code in (200, 201):
            success += len(batch)
            print(f"  ✓ Batch {i//batch_size + 1}: inserted {len(batch)} records ({success} total)")
        else:
            print(f"  ✗ Batch {i//batch_size + 1} failed: {r.status_code} {r.text[:150]}")

    print(f"\nDone. {success}/{len(records)} records inserted.")
    print(f"Dashboard at: https://threat-vector.vercel.app")


if __name__ == "__main__":
    seed()
