"""
Seed 10,000 synthetic threat tips into Supabase via REST API.
Run: python3 seed_10k_tips.py
"""
import os, uuid, random, json, sys
import urllib.request, urllib.error
from datetime import datetime, timedelta

# ── Load .env manually (avoid importing dotenv which might shadow something) ───
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    sys.exit("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

def sb_insert(rows: list) -> bool:
    url  = f"{SUPABASE_URL}/rest/v1/tips"
    data = json.dumps(rows).encode()
    req  = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status in (200, 201)
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"\n  HTTP {e.code}: {body}")
        return False

# ── Reference data ─────────────────────────────────────────────────────────────

SCHOOLS = [
    "Westbrook Academy","Lincoln High School","Jefferson Middle School",
    "Roosevelt Elementary","Madison High School","Franklin Academy",
    "Washington High School","Adams Middle School","Monroe Elementary",
    "Jackson Academy","Desert Ridge Academy","Pacific Crest High School",
    "Oakwood Middle School","Riverside Academy","Northgate High School",
    "Southside Elementary","Eastview Academy","Central High School",
    "Valley Prep School","Hillcrest Middle School","Lakeside Academy",
    "Maplewood High School","Pinecrest Elementary","Cedarview Academy",
    "Elm Street Middle School","Birchwood High School","Willow Creek Academy",
    "Stonegate High School","Creekside Middle School","Summit Academy",
    "Horizon High School","Sunrise Elementary","Clearwater Academy",
    "Greenfield High School","Meadowbrook Middle School","Fairview Academy",
    "Bridgewater High School","Harborview Elementary","Cliffside Academy",
    "Woodland High School","Springbrook Middle School","Glendale Academy",
    "Silver Lake High School","Redwood Elementary","Bayview Academy",
    "Mountainview High School","Riverbend Middle School","Prairieview Academy",
    "Goldenview High School","Foxhill Elementary",
]

CATEGORIES = ["weapon","threat","bullying","drugs","self_harm","vandalism","harassment","other"]
CAT_WEIGHTS = [8, 15, 20, 12, 8, 10, 12, 15]

URGENCY_POOL = (["critical"]*6 + ["high"]*18 + ["medium"]*44 + ["low"]*32)

EMOTIONS   = ["calm","anxious","panicked","distressed","detached","nervous","angry"]
TONES      = ["urgent","calm","whispered","crying","matter-of-fact","frightened","hesitant"]
ESCALATION = ["stable"]*3 + ["escalating"]*2 + ["imminent"]
TIMELINES  = ["today","this_week","next_week","this_month","unknown","past"]
ACTIONS    = ["immediate_response","investigate","counselor_followup","monitor","contact_parents","law_enforcement"]
STATUSES   = ["new","new","new","reviewing","dismissed"]

CAT_SUMMARIES = {
    "weapon":     ["Student showing weapon photos to classmates","Anonymous tip about student bringing firearm","Caller witnessed student with knife in bathroom","Social media post shows student with weapon","Student threatened peers and claimed to have a gun","Parent reports weapon seen in student's backpack","Student overheard discussing bringing a weapon","Tip about student trading ammunition in parking lot"],
    "threat":     ["Written threat found in bathroom targeting teacher","Student made explicit verbal threats to shoot school","Anonymous note placed in lockers threatening violence","Social media post with specific date and target","Student told multiple peers about planned attack","Threatening message sent in group chat of 50+ students","Student drew violent imagery with names of targets","Online post identified by counselor as credible threat"],
    "bullying":   ["Ongoing physical bullying escalating to threats","Group systematically targeting one student","Cyberbullying forcing student to consider self-harm","Student physically assaulted in locker room repeatedly","Lunch intimidation and food theft reported by multiple students","Student recording embarrassing videos without consent"],
    "drugs":      ["Student selling pills in school bathroom","Vape pens being distributed at bus stop","Unknown powder substance found in student's desk","Student arrived visibly intoxicated to first period","Pills found in shared locker not matching prescription"],
    "self_harm":  ["Student expressing suicidal ideation to close friend","Self-harm marks observed by PE teacher","Student giving away personal belongings — concerning","Anonymous tip about student planning to hurt themselves","Student wrote farewell letters found by parent"],
    "vandalism":  ["Threatening graffiti found in gym locker room overnight","Car windows smashed targeting specific student","Classroom destruction with racial slurs spray painted","School equipment damaged and threatening message left"],
    "harassment": ["Sexual harassment campaign targeting female student","Racial slurs and intimidation reported in hallways","Teacher receiving threatening anonymous messages","Student being stalked by peer on and off campus"],
    "other":      ["Suspicious vehicle parked outside school multiple days","Unknown adult attempting to contact students at dismissal","Suspicious package left near main entrance","Student reported suspicious activity in adjacent building"],
}

KEYWORDS = {
    "weapon":     ["weapon","gun","knife","firearm","ammo"],
    "threat":     ["threat","kill","attack","hurt","revenge"],
    "bullying":   ["bully","fight","intimidate","target","victim"],
    "drugs":      ["pills","vape","powder","substance"],
    "self_harm":  ["hurt myself","suicide","end it","farewell"],
    "vandalism":  ["graffiti","damage","destroy","smash"],
    "harassment": ["harass","stalk","intimidate","slurs"],
    "other":      ["suspicious","unknown","strange"],
}

def random_date():
    return (datetime.utcnow() - timedelta(
        days=random.randint(0, 730),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59)
    )).strftime("%Y-%m-%dT%H:%M:%SZ")

def make_tip() -> dict:
    school   = random.choice(SCHOOLS)
    category = random.choices(CATEGORIES, weights=CAT_WEIGHTS)[0]
    urgency  = random.choice(URGENCY_POOL)
    emotion  = random.choice(EMOTIONS)
    tone     = random.choice(TONES)
    status   = random.choice(STATUSES)
    created  = random_date()
    summary  = random.choice(CAT_SUMMARIES[category])
    kws      = random.sample(KEYWORDS[category], min(3, len(KEYWORDS[category])))

    score = {"critical": random.randint(85,99), "high": random.randint(65,84),
             "medium": random.randint(35,64), "low": random.randint(5,34)}[urgency]
    gemini_lvl = {"critical":5,"high":random.randint(3,4),"medium":random.randint(2,3),"low":random.randint(1,2)}[urgency]
    bayes_pct  = min(99, score + random.randint(-8, 8))
    consensus  = random.random() > 0.2
    three_mdl  = consensus and abs(score - bayes_pct) < 15

    cross = None
    if urgency in ("critical","high") and random.random() < 0.07:
        other = random.choice([s for s in SCHOOLS if s != school])
        cross = f"Similar {category} threat at {other} — possible coordinated pattern"

    drivers = [{"keyword": kw, "feature": f"{category}_{kw.replace(' ','_')}", "ratio": round(random.uniform(1.5,4.5),2)} for kw in kws]
    key_facts = random.sample([
        f"Anonymous report from {school}",
        "Multiple student witnesses corroborate",
        f"Escalating pattern of {category} incidents",
        "Specific timeline mentioned by caller",
        f"Caller was {emotion} and {tone}",
        f"Call lasted {random.randint(20,200)} seconds",
    ], k=random.randint(2,4))

    dispatch = None
    if urgency == "critical":
        dispatch = f"CRITICAL — {category.upper()}\nSchool: {school}\nLevel: 5/5\nAction: IMMEDIATE RESPONSE\n{summary}"

    # Only use columns confirmed to exist in the base schema
    return {
        "id":                    str(uuid.uuid4()),
        "description":           summary,
        "category":              category,
        "urgency":               urgency,
        "severity":              urgency,
        "status":                status,
        "is_anonymous":          True,
        "ai_summary":            summary,
        "ai_triage_score":       score,
        "ai_recommended_action": random.choice(ACTIONS),
        "school_name":           school,
        "created_at":            created,
        "submitted_at":          created,
    }

# ── Run ─────────────────────────────────────────────────────────────────────────

TOTAL = 10_000
BATCH = 200   # smaller batches to stay under payload limits

print(f"Generating {TOTAL:,} synthetic threat tips...")
tips = [make_tip() for _ in range(TOTAL)]

print(f"Inserting in batches of {BATCH} into {SUPABASE_URL}...")
inserted = 0
errors   = 0

for start in range(0, TOTAL, BATCH):
    batch = tips[start : start + BATCH]
    ok = sb_insert(batch)
    if ok:
        inserted += len(batch)
    else:
        errors += len(batch)
    pct = (start + len(batch)) / TOTAL * 100
    bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
    print(f"\r  [{bar}] {inserted:,} inserted  {errors:,} errors  ({pct:.0f}%)", end="", flush=True)

print(f"\n\n✓ Complete — {inserted:,} tips in Supabase")
print(f"  critical: {sum(1 for t in tips if t['urgency']=='critical')}  "
      f"high: {sum(1 for t in tips if t['urgency']=='high')}  "
      f"medium: {sum(1 for t in tips if t['urgency']=='medium')}  "
      f"low: {sum(1 for t in tips if t['urgency']=='low')}")
print(f"  Schools: {len(set(t['school_name'] for t in tips))}")
