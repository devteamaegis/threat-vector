#!/usr/bin/env python3
"""
Seed Supermemory with the 200-record historical threat database.
Run once before the demo so every incoming call has historical context.

Usage: python seed_supermemory.py
"""
import os, json, time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

from supermemory import Supermemory

CONTAINER_TAG = "threat-vector-tips"

# Historical threat records drawn from FBI/CHDS/NTAC patterns
# Each record represents a real threat category with realistic outcomes
HISTORICAL_THREATS = [
    # WEAPON THREATS — Level 4-5
    {"id": "hist-001", "school": "Westbrook Academy", "category": "weapon", "level": 5,
     "description": "Student showed firearm to peers before school, made explicit threats for Friday. Prior suspension, escalating over weeks.",
     "outcome": "credible — law enforcement responded, weapon recovered, student arrested",
     "timeline": "this_week", "escalation": "imminent", "emotion": "distressed"},
    {"id": "hist-002", "school": "Lincoln High School", "category": "weapon", "level": 5,
     "description": "Anonymous tip: student posted photos of gun on social media with threatening captions targeting specific teachers.",
     "outcome": "credible — social media posts confirmed, weapon secured by family",
     "timeline": "today", "escalation": "imminent", "emotion": "distressed"},
    {"id": "hist-003", "school": "Jefferson Middle School", "category": "weapon", "level": 4,
     "description": "Student overheard saying they have a knife and 'will use it if pushed' after fight with another student.",
     "outcome": "credible — knife found in locker search",
     "timeline": "today", "escalation": "escalating", "emotion": "panicked"},
    {"id": "hist-004", "school": "Palmview High School", "category": "weapon", "level": 5,
     "description": "Caller reports seeing student with what appeared to be a handgun in backpack during passing period.",
     "outcome": "credible — weapon confirmed, lockdown executed",
     "timeline": "now", "escalation": "imminent", "emotion": "panicked"},
    {"id": "hist-005", "school": "Prairie View High School", "category": "weapon", "level": 4,
     "description": "Student threatened to bring weapon after suspension for fighting. Has made similar threats before.",
     "outcome": "credible — student had weapon at home, family intervention required",
     "timeline": "next_week", "escalation": "escalating", "emotion": "anxious"},
    {"id": "hist-006", "school": "Desert Ridge Academy", "category": "weapon", "level": 3,
     "description": "Rumor circulating that a student mentioned having a gun. No direct witness, second-hand report.",
     "outcome": "unsubstantiated — investigation found no evidence",
     "timeline": "unknown", "escalation": "stable", "emotion": "calm"},
    {"id": "hist-007", "school": "Pacific Crest High School", "category": "weapon", "level": 5,
     "description": "Parent called reporting their child found a loaded firearm in another student's unlocked locker.",
     "outcome": "credible — weapon confirmed and removed",
     "timeline": "now", "escalation": "imminent", "emotion": "panicked"},
    {"id": "hist-008", "school": "Riverside Preparatory", "category": "weapon", "level": 4,
     "description": "Student texted friends about bringing gun to school tomorrow. Screenshots shared with school.",
     "outcome": "credible — student admitted to access to firearms, counseling initiated",
     "timeline": "tomorrow", "escalation": "escalating", "emotion": "distressed"},

    # BULLYING / HARASSMENT — Level 2-3
    {"id": "hist-009", "school": "Northgate High School", "category": "bullying", "level": 3,
     "description": "Severe cyberbullying targeting student with special needs. Group chat with 40+ students sharing degrading content.",
     "outcome": "credible — students disciplined, victim received counseling",
     "timeline": "ongoing", "escalation": "escalating", "emotion": "distressed"},
    {"id": "hist-010", "school": "Cypress Creek High", "category": "bullying", "level": 2,
     "description": "Physical bullying in locker room after PE. Student being repeatedly hit and has bruises.",
     "outcome": "credible — bullies identified and suspended",
     "timeline": "ongoing", "escalation": "stable", "emotion": "anxious"},
    {"id": "hist-011", "school": "Magnolia Ridge Academy", "category": "harassment", "level": 3,
     "description": "Student receiving threatening notes in locker, including one saying 'you won't make it to graduation'.",
     "outcome": "credible — perpetrator identified via fingerprints",
     "timeline": "ongoing", "escalation": "escalating", "emotion": "distressed"},
    {"id": "hist-012", "school": "Heritage Academy", "category": "harassment", "level": 2,
     "description": "Racial harassment targeting multiple students in one grade. Slurs written on lockers.",
     "outcome": "credible — hate crime referral, sensitivity training implemented",
     "timeline": "ongoing", "escalation": "stable", "emotion": "anxious"},

    # SELF-HARM / MENTAL HEALTH — Level 3-4
    {"id": "hist-013", "school": "Oakdale Academy", "category": "self_harm", "level": 4,
     "description": "Student told friends goodbye and posted farewell messages. Has been isolated and withdrawn for two weeks.",
     "outcome": "credible — student found with pills, hospitalized, recovering",
     "timeline": "today", "escalation": "imminent", "emotion": "detached"},
    {"id": "hist-014", "school": "Riverdale High School", "category": "self_harm", "level": 3,
     "description": "Caller concerned about friend showing visible self-harm marks and saying 'there's no point anymore'.",
     "outcome": "credible — intervention successful, student received mental health support",
     "timeline": "ongoing", "escalation": "escalating", "emotion": "distressed"},
    {"id": "hist-015", "school": "Centennial Middle School", "category": "self_harm", "level": 4,
     "description": "Student told teacher they had a plan to end their life this weekend. Specific method mentioned.",
     "outcome": "credible — emergency psychiatric evaluation, 72-hour hold",
     "timeline": "this_week", "escalation": "imminent", "emotion": "detached"},
    {"id": "hist-016", "school": "Suncoast Middle School", "category": "self_harm", "level": 3,
     "description": "Student has been giving away their belongings to classmates. Has history of depression.",
     "outcome": "credible — student in crisis, family notified, counseling started",
     "timeline": "today", "escalation": "escalating", "emotion": "detached"},

    # DRUGS — Level 2-3
    {"id": "hist-017", "school": "Pinecrest Academy", "category": "drugs", "level": 3,
     "description": "Student selling pills identified as Xanax to multiple students in bathroom. Has been doing this for weeks.",
     "outcome": "credible — student arrested, 14 pills recovered",
     "timeline": "ongoing", "escalation": "stable", "emotion": "calm"},
    {"id": "hist-018", "school": "Crossroads High School", "category": "drugs", "level": 2,
     "description": "Cannabis smell coming from bathroom. Several students appear impaired during second period.",
     "outcome": "credible — 3 students found with marijuana",
     "timeline": "now", "escalation": "stable", "emotion": "calm"},
    {"id": "hist-019", "school": "Cactus Valley High School", "category": "drugs", "level": 3,
     "description": "Student passed out at lunch, classmates believe it was from fentanyl-laced pills. Multiple witnesses.",
     "outcome": "credible — student overdose, Narcan administered, survived",
     "timeline": "now", "escalation": "imminent", "emotion": "panicked"},
    {"id": "hist-020", "school": "Sunridge High School", "category": "drugs", "level": 3,
     "description": "Vape devices with THC cartridges being sold near bus stop before school. Ongoing operation.",
     "outcome": "credible — 2 students expelled, distributor referred to police",
     "timeline": "ongoing", "escalation": "stable", "emotion": "calm"},

    # EXPLICIT SHOOTING THREATS — Level 5
    {"id": "hist-021", "school": "Mesa View Middle", "category": "threat", "level": 5,
     "description": "Student wrote manifesto found in notebook planning attack on school, listing specific targets and date.",
     "outcome": "credible — emergency expulsion, weapons found at home, arrested",
     "timeline": "this_week", "escalation": "imminent", "emotion": "detached"},
    {"id": "hist-022", "school": "Canyon View Academy", "category": "threat", "level": 5,
     "description": "Caller overheard student say he was 'going to do what those other guys did' referencing school shootings.",
     "outcome": "credible — student had detailed plan and access to firearms",
     "timeline": "this_week", "escalation": "imminent", "emotion": "calm"},
    {"id": "hist-023", "school": "Horizon High School", "category": "threat", "level": 5,
     "description": "Anonymous note found in bathroom: 'There's a bomb in this school. Evacuate now or people will die.'",
     "outcome": "unsubstantiated — full sweep found nothing, note treated as hoax",
     "timeline": "now", "escalation": "imminent", "emotion": "panicked"},
    {"id": "hist-024", "school": "Golden Gate Academy", "category": "threat", "level": 4,
     "description": "Student made mass shooting threat on school's social media page after being bullied. Post went viral.",
     "outcome": "credible — student had access to firearms, psychiatric hold",
     "timeline": "tomorrow", "escalation": "escalating", "emotion": "distressed"},
    {"id": "hist-025", "school": "Valley View High School", "category": "threat", "level": 4,
     "description": "Student told multiple friends 'Monday will be my last day here' with no context for transfer or graduation.",
     "outcome": "credible — student had written notes and researched attacks",
     "timeline": "this_week", "escalation": "escalating", "emotion": "detached"},

    # VANDALISM / PROPERTY — Level 1-2
    {"id": "hist-026", "school": "Eastside Academy", "category": "vandalism", "level": 2,
     "description": "Graffiti with threatening language targeting specific student group found in multiple bathrooms.",
     "outcome": "credible — perpetrator identified on security cameras",
     "timeline": "yesterday", "escalation": "stable", "emotion": "calm"},
    {"id": "hist-027", "school": "Lakewood High School", "category": "vandalism", "level": 1,
     "description": "Lockers of several students keyed with slurs. Appears targeted.",
     "outcome": "credible — hate incident report filed",
     "timeline": "yesterday", "escalation": "stable", "emotion": "calm"},

    # MORE WEAPON THREATS for pattern density
    {"id": "hist-028", "school": "Sierra View Academy", "category": "weapon", "level": 5,
     "description": "Student making specific threats on Discord server with photo of gun. Multiple students screenshotted and reported.",
     "outcome": "credible — weapon at home, student arrested",
     "timeline": "today", "escalation": "imminent", "emotion": "distressed"},
    {"id": "hist-029", "school": "Redwood High School", "category": "weapon", "level": 4,
     "description": "Student bragging to friends about having a gun in car in school parking lot.",
     "outcome": "credible — firearm found in vehicle",
     "timeline": "now", "escalation": "escalating", "emotion": "calm"},
    {"id": "hist-030", "school": "Coastline Middle School", "category": "weapon", "level": 3,
     "description": "Student showed what appeared to be a knife to classmates during lunch. Other students reported feeling scared.",
     "outcome": "credible — pocket knife recovered",
     "timeline": "now", "escalation": "stable", "emotion": "anxious"},

    # THREATS WITH BEHAVIORAL BUILD-UP (escalation pattern — key for Supermemory matching)
    {"id": "hist-031", "school": "Westbrook Academy", "category": "threat", "level": 4,
     "description": "Follow-up tip: same student from last week still threatening peers, now saying he has access to something 'bigger'.",
     "outcome": "credible — escalation confirmed, second weapon found",
     "timeline": "this_week", "escalation": "escalating", "emotion": "distressed"},
    {"id": "hist-032", "school": "Lincoln High School", "category": "threat", "level": 3,
     "description": "Student's behavior has been increasingly erratic — destroying own belongings, isolating from friends, stopped caring about grades.",
     "outcome": "credible — mental health crisis, not weapon threat, but intervention needed",
     "timeline": "ongoing", "escalation": "escalating", "emotion": "detached"},
    {"id": "hist-033", "school": "Prairie View High School", "category": "weapon", "level": 5,
     "description": "Parent reports finding ammunition in child's room. Child has been fixated on school shootings and 'getting revenge'.",
     "outcome": "credible — additional weapons found, student hospitalized",
     "timeline": "this_week", "escalation": "imminent", "emotion": "detached"},
    {"id": "hist-034", "school": "Palmview High School", "category": "threat", "level": 4,
     "description": "Student has sent 3 threatening messages to school email in past month. Tone is escalating.",
     "outcome": "credible — student had access to firearms, TRO issued",
     "timeline": "ongoing", "escalation": "escalating", "emotion": "distressed"},
    {"id": "hist-035", "school": "Desert Ridge Academy", "category": "threat", "level": 5,
     "description": "Student has been making increasingly specific threats. Started with vague comments 3 weeks ago, now naming classrooms and times.",
     "outcome": "credible — specific planning confirmed, pre-attack behavior present",
     "timeline": "this_week", "escalation": "imminent", "emotion": "detached"},
]

# Generate additional records to reach 200 with varied patterns
import random

SCHOOLS_EXTRA = [
    "Westview Academy", "Summit High School", "Elmwood Middle School",
    "Riverside High School", "Northfield Academy", "Greenwood High",
    "Maplewood Middle School", "Clearwater High School", "Stonegate Academy",
    "Hillcrest High School", "Brookside Middle School", "Fairview Academy",
    "Meadowbrook High School", "Lakeside Academy", "Springdale High School",
]

EXTRA_PATTERNS = [
    ("weapon", 5, "Student posted on social media about bringing a weapon to school, with photos of firearms. Multiple students alarmed.", "credible — weapon secured"),
    ("weapon", 4, "Anonymous caller reports student showing off gun in bathroom between classes.", "credible — weapon recovered"),
    ("weapon", 3, "Student threatened to 'bring something' to school after altercation with another student.", "unsubstantiated — no weapon found"),
    ("threat", 5, "Student created list of targets and was overheard discussing timing of attack.", "credible — planning confirmed"),
    ("threat", 4, "Student making increasingly violent statements after recent breakup, researching school attacks online.", "credible — intervention required"),
    ("threat", 3, "Student told classmate there would be 'something big' happening at school next week.", "unsubstantiated — hoax confirmed"),
    ("self_harm", 4, "Multiple students concerned about peer who has been saying goodbye and giving away possessions.", "credible — crisis intervention"),
    ("self_harm", 3, "Student showing signs of severe depression, stopped attending class, visible self-harm marks.", "credible — counseling initiated"),
    ("bullying", 3, "Systematic bullying campaign targeting transfer student. Physical and online components.", "credible — perpetrators disciplined"),
    ("drugs", 3, "Student distributing pills at lunch. At least 5 students known to have taken them.", "credible — opioids confirmed"),
    ("drugs", 2, "Vaping in bathroom becoming organized — students taking turns as lookout.", "credible — multiple devices confiscated"),
    ("harassment", 3, "Sexual harassment campaign targeting female students in a specific grade.", "credible — Title IX investigation"),
    ("vandalism", 2, "Threatening graffiti in multiple locations targeting specific ethnic group.", "credible — hate incident"),
    ("weapon", 5, "Parent found loaded pistol in child's backpack. Child refuses to say where they got it.", "credible — weapon recovered, source investigated"),
    ("threat", 5, "Student made specific threat including date, method, and target list in a journal found by teacher.", "credible — pre-attack planning, arrested"),
]

EMOTIONS = ["calm", "distressed", "panicked", "anxious", "detached"]
TIMELINES = ["now", "today", "tomorrow", "this_week", "next_week", "ongoing"]
ESCALATIONS = ["stable", "escalating", "imminent"]


def generate_records():
    records = list(HISTORICAL_THREATS)
    random.seed(42)
    idx = 36
    for i in range(165):  # fill to 200
        pattern = random.choice(EXTRA_PATTERNS)
        school = random.choice(SCHOOLS_EXTRA)
        category, level, desc, outcome = pattern
        records.append({
            "id": f"hist-{idx:03d}",
            "school": school,
            "category": category,
            "level": level,
            "description": desc,
            "outcome": outcome,
            "timeline": random.choice(TIMELINES),
            "escalation": random.choice(ESCALATIONS),
            "emotion": random.choice(EMOTIONS),
        })
        idx += 1
    return records


def seed_supermemory():
    key = os.getenv("SUPERMEMORY_API_KEY", "")
    if not key or key == "FILL_IN":
        print("ERROR: SUPERMEMORY_API_KEY not set in .env")
        return

    client = Supermemory(api_key=key)
    records = generate_records()
    print(f"Seeding {len(records)} historical threat records into Supermemory...")

    success = 0
    failed = 0
    for i, threat in enumerate(records):
        content = (
            f"Historical: {threat['description']} at {threat['school']}. "
            f"Type: {threat['category']}. Level: {threat['level']}/5. "
            f"Timeline: {threat['timeline']}. "
            f"Escalation: {threat['escalation']}. "
            f"Caller emotion: {threat['emotion']}. "
            f"Outcome: {threat['outcome']}."
        )
        try:
            client.add(
                content=content,
                container_tag="threat-vector-tips",
                custom_id=threat["id"],
                metadata={
                    "school": threat["school"],
                    "level": str(threat["level"]),
                    "threat_type": threat["category"],
                    "historical": "true",
                    "outcome": threat["outcome"][:50],
                },
            )
            success += 1
            if (i + 1) % 20 == 0:
                print(f"  {i+1}/{len(records)} seeded...")
            time.sleep(0.15)  # gentle rate limiting
        except Exception as e:
            failed += 1
            print(f"  FAILED {threat['id']}: {e}")

    print(f"\n✓ Done: {success} seeded, {failed} failed")
    print(f"  Supermemory now has {success} historical threat records for pattern matching.")
    print(f"  Every new incoming call will be matched against this database.")


if __name__ == "__main__":
    seed_supermemory()
