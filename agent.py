import asyncio
import math
import os
import re
import requests
from classifier import classify_threat, generate_email_brief
from osint import run_osint
from notify import send_sms_alert, send_email_brief
from memory import store_tip_memory, search_prior_tips
from supabase import log_tip_to_aegis, update_tip_geo, update_tip_enriched
from moss_search import semantic_search_tips, index_tip
from stripe_billing import charge_for_tip
from sponge_payments import disburse_agent_payment, authorize_background_check, log_transaction_to_supabase, run_paid_background_check
from gemini_verify import gemini_verify
from gemini_live import live_multilingual_analysis
from aws_archive import archive_transcript
from deepgram_transcribe import transcribe_audio_url
from attendance_handler import log_attendance
from bayesian_scorer import monte_carlo_score, probability_to_level
from cross_school_detector import detect_cross_school_pattern
from predict_window import predict_threat_window
from dispatch_brief import format_dispatch_brief
from datetime import datetime

_GEO_CACHE: dict[str, tuple[float, float] | None] = {}
LOCATION_KEYWORDS = ("room", "gym", "cafeteria", "parking", "hallway", "bathroom", "auditorium", "library")

async def _run_sync_with_timeout(func, timeout: int, *args, **kwargs):
    return await asyncio.wait_for(asyncio.to_thread(func, *args, **kwargs), timeout=timeout)

def geolocate_school(school_name: str) -> tuple[float, float] | None:
    school = (school_name or "").strip()
    if not school or school.lower() == "unknown school":
        return None
    if school in _GEO_CACHE:
        return _GEO_CACHE[school]
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": school, "format": "json", "limit": 1},
            headers={"User-Agent": "ThreatVector/1.0 school-safety-demo"},
            timeout=8,
        )
        if response.status_code != 200:
            _GEO_CACHE[school] = None
            return None
        data = response.json()
        if not data:
            _GEO_CACHE[school] = None
            return None
        coords = (float(data[0]["lat"]), float(data[0]["lon"]))
        _GEO_CACHE[school] = coords
        return coords
    except Exception:
        _GEO_CACHE[school] = None
        return None

# ── Spoken address extraction + geocoding ─────────────────────────────────────
_SPOKEN_DIGITS = {
    'zero':'0','one':'1','two':'2','three':'3','four':'4',
    'five':'5','six':'6','seven':'7','eight':'8','nine':'9',
}
_STREET_TYPES = r'(?:road|street|avenue|drive|lane|boulevard|way|place|court|circle|blvd|ave|dr|st|rd|ln|ct|pl|highway|hwy)'

def _normalize_spoken_number(tokens: list[str]) -> str:
    """Convert a list of digit-word tokens to a numeric string. 'one four one five eight' → '14158'."""
    return ''.join(_SPOKEN_DIGITS.get(t.lower(), t) for t in tokens)

def _extract_spoken_address(transcript: str) -> str | None:
    """
    Extract a street address from spoken transcript where the caller read
    digits individually: 'one four one five eight at Gallup Road' → '14158 Gallup Road'.
    Also handles normal numeric form: '14158 Gallup Road'.
    """
    t = transcript.strip()

    # 1. Normal numeric address: "14158 Gallup Road"
    m = re.search(
        rf'\b(\d{{2,6}})\s+((?:[A-Z][a-zA-Z]+\s*){{1,4}}{_STREET_TYPES})\b',
        t, re.IGNORECASE,
    )
    if m:
        return f"{m.group(1)} {m.group(2).strip()}"

    # 2. Spoken digit-by-digit: "one four one five eight at Gallup Road"
    digit_word = '|'.join(_SPOKEN_DIGITS.keys())
    # Match: <digits spoken individually> + optional 'at'/'on' + <street>
    pattern = (
        rf'\b((?:(?:{digit_word})\s+){{2,6}})'           # 2-6 spoken digits
        rf'(?:at\s+|on\s+|in\s+)?'                        # optional preposition
        rf'((?:[A-Z][a-zA-Z]+\s*){{1,4}}{_STREET_TYPES})\b'  # street name
    )
    m2 = re.search(pattern, t, re.IGNORECASE)
    if m2:
        digit_tokens = m2.group(1).strip().split()
        number_str = _normalize_spoken_number(digit_tokens)
        street = m2.group(2).strip()
        return f"{number_str} {street}"

    return None


def _geocode_address(address: str, call_id: str = "system") -> tuple[float, float] | None:
    """Geocode a street address via Nominatim (free, no API key needed)."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1, "addressdetails": 1},
            headers={"User-Agent": "ThreatVector/1.0 school-safety-demo"},
            timeout=6,
        )
        if r.ok and r.json():
            hit = r.json()[0]
            lat, lng = float(hit["lat"]), float(hit["lon"])
            print(f"[{call_id}] Address geocode: '{address}' → ({lat:.4f}, {lng:.4f})")
            return lat, lng
    except Exception as e:
        print(f"[{call_id}] WARNING: address geocode failed for '{address}': {e}")
    return None


def _caller_coords(caller_location: dict | None) -> tuple[float, float] | None:
    if not caller_location:
        return None
    lat = caller_location.get("lat") or caller_location.get("latitude") or caller_location.get("call_lat")
    lng = caller_location.get("lng") or caller_location.get("lon") or caller_location.get("longitude") or caller_location.get("call_lng")
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return None
    if math.isfinite(lat_f) and math.isfinite(lng_f):
        return lat_f, lng_f
    return None

def _extract_named_subject_from_transcript(transcript: str) -> str | None:
    """
    Extract a full person name from a transcript using regex patterns.
    Handles: "threatening Max Higgins", "kill John Smith", "his name is ...", etc.
    Returns the most likely full name (First Last) or None.
    """
    t = transcript.strip()
    # Patterns that introduce a person's name as the subject of a threat
    patterns = [
        # "kill/hurt/shoot/threaten [Name]"
        r'(?:kill|hurt|shoot|attack|threaten(?:ing)?|going after|find)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
        # "his name is / her name is / the student named"
        r'(?:his|her|their)\s+name\s+is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})',
        r'(?:student|person|guy|kid|man|woman)\s+named\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})',
        # "named [Name]" or "called [Name]"
        r'\bnamed\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
        # "threatening [Name]" at start of phrase
        r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:is the target|is going to be|will be)',
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            name = m.group(1).strip()
            # Sanity check: must be 2 words (First Last), not a common word
            words = name.split()
            skip_words = {'The', 'This', 'That', 'School', 'Student', 'Teacher', 'Gun', 'Bomb', 'Knife'}
            if len(words) >= 2 and not any(w in skip_words for w in words):
                return name
    return None


def _extract_location_context(classification: dict) -> str | None:
    sources = []
    facts = classification.get("key_facts") or []
    if isinstance(facts, list):
        sources.extend(str(f) for f in facts)
    brief = classification.get("dispatch_brief")
    if brief:
        sources.append(str(brief))
    for text in sources:
        lowered = text.lower()
        if any(k in lowered for k in LOCATION_KEYWORDS):
            match = re.search(
                r"((?:room\s+\w+)|(?:\w+\s+gym)|(?:gym)|(?:cafeteria)|(?:parking\s+(?:lot\s*)?\w*)|(?:hallway)|(?:bathroom)|(?:auditorium)|(?:library))",
                text,
                re.IGNORECASE,
            )
            return (match.group(1) if match else text).strip()[:160]
    return None

async def run_threat_agent(
    call_id: str,
    transcript: str,
    recording_url: str | None = None,
    call_duration_seconds: int = 0,
    caller_location: dict | None = None,
):
    print(f"[{call_id}] Starting threat agent pipeline...")
    pipeline_errors: list[str] = []

    deepgram_result = {}
    if recording_url:
        try:
            print(f"[{call_id}] Deepgram: re-transcribing call recording...")
            deepgram_result = await _run_sync_with_timeout(transcribe_audio_url, 10, recording_url, call_id)
            if deepgram_result.get("confidence", 0) > 0.85 and deepgram_result.get("transcript"):
                transcript = deepgram_result["transcript"]
                print(f"[{call_id}] Deepgram: using transcript with {deepgram_result['confidence']:.2f} confidence")
        except Exception as e:
            pipeline_errors.append("deepgram")
            print(f"[{call_id}] WARNING: Deepgram failed: {e}")

    # ── Gemini Live: multilingual detection FIRST so all downstream uses English ─
    # Running this before classify_threat means Spanish/French/etc. calls get
    # translated before Claude, Bayesian scorer, and OSINT ever see the text.
    print(f"[{call_id}] Gemini Live: multilingual real-time analysis...")
    try:
        live_result = await asyncio.wait_for(live_multilingual_analysis(transcript, call_id), timeout=12)
    except Exception as e:
        pipeline_errors.append("gemini_live")
        print(f"[{call_id}] WARNING: Gemini Live failed: {e}")
        live_result = {
            "detected_language": "English",
            "english_translation": None,
            "multilingual": False,
        }

    if live_result.get("multilingual") and live_result.get("english_translation"):
        lang = live_result["detected_language"]
        print(f"[{call_id}] Non-English call detected: {lang} — using translation for all downstream steps")
        working_transcript = live_result["english_translation"]
        classification_note = f"[Original language: {lang}. Auto-translated by Gemini Live.]"
    else:
        working_transcript = transcript
        classification_note = ""

    # ── Attendance quick-check: classify call type before entering threat pipeline
    # Uses working_transcript (already translated if non-English)
    try:
        classification = await _run_sync_with_timeout(classify_threat, 20, working_transcript)
    except Exception as e:
        pipeline_errors.append("claude_classification")
        print(f"[{call_id}] WARNING: Claude classification failed: {e}")
        classification = {
            "call_type": "general",
            "threat_level": 3,
            "threat_type": "other",
            "summary": working_transcript[:240],
            "school_name": "Unknown School",
            "recommended_action": "manual_review",
        }

    classification["pipeline_errors"] = pipeline_errors

    if classification.get("call_type") == "attendance":
        print(f"[{call_id}] Attendance call detected — skipping threat pipeline")
        log_attendance(classification, call_id)
        return classification

    # ── Moss: semantic context search ─────────────────────────────────────────
    print(f"[{call_id}] Moss: semantic context search...")
    try:
        moss_context = await _run_sync_with_timeout(semantic_search_tips, 5, working_transcript[:300], call_id)
    except Exception as e:
        pipeline_errors.append("moss_search")
        print(f"[{call_id}] WARNING: Moss search failed: {e}")
        moss_context = ""
    if moss_context:
        print(f"[{call_id}] Moss context: {moss_context[:80]}...")

    # ── Claude: final classification with Moss context + language note ────────
    print(f"[{call_id}] Claude: classifying threat...")
    enriched_transcript = working_transcript
    if moss_context:
        enriched_transcript = f"{working_transcript}\n\n[Prior semantic context: {moss_context}]"
    if classification_note:
        enriched_transcript = f"{classification_note}\n\n{enriched_transcript}"

    try:
        classification = await _run_sync_with_timeout(classify_threat, 20, enriched_transcript)
    except Exception as e:
        pipeline_errors.append("claude_enriched_classification")
        print(f"[{call_id}] WARNING: Enriched Claude classification failed: {e}")

    # Carry multilingual metadata into classification for Supabase storage
    if live_result.get("multilingual"):
        classification.setdefault("caller_language", live_result.get("detected_language"))
        classification.setdefault("multilingual_call", True)
        classification.setdefault("english_translation", live_result.get("english_translation"))

    classification["pipeline_errors"] = pipeline_errors
    claude_level = classification.get("threat_level", 3)
    school = classification.get("school_name", "Unknown School")
    print(f"[{call_id}] Claude: level {claude_level}/5, school: {school}")

    # Ensure call_duration_seconds is set before early INSERT
    if call_duration_seconds == 0 and transcript.strip():
        call_duration_seconds = max(5, len(transcript.split()) // 2)
    classification["call_duration_seconds"] = call_duration_seconds

    # ── EARLY Supabase INSERT: show card on dashboard NOW (~18s from call end) ─
    # The dashboard sees this tip immediately. We'll PATCH with enrichment next.
    print(f"[{call_id}] Supabase: EARLY INSERT — making tip visible on dashboard...")
    tip_id = log_tip_to_aegis(classification, transcript, call_id, "")
    print(f"[{call_id}] Supabase: preliminary tip ID {tip_id} — dashboard updating now")

    # Seed coords from caller GPS if present; geocode school otherwise (done in parallel)
    coords = _caller_coords(caller_location)

    # ── PARALLEL ENRICHMENT: two branches run concurrently ───────────────────
    # Branch A: Moss semantic search → Claude #2 (enriched classification)
    # Branch B: Geocode + Bayesian MC + Gemini verify + Supermemory (all independent)
    # Total wall time ≈ max(branch_A, branch_B) instead of sum.

    async def _branch_moss_claude():
        """Moss context search → second Claude classification with context."""
        ctx = ""
        try:
            print(f"[{call_id}] Moss: semantic context search...")
            ctx = await _run_sync_with_timeout(semantic_search_tips, 5, working_transcript[:300], call_id)
            if ctx:
                print(f"[{call_id}] Moss context: {ctx[:80]}...")
        except Exception as e:
            pipeline_errors.append("moss_search")
            print(f"[{call_id}] WARNING: Moss search failed: {e}")

        enriched = working_transcript
        if ctx:
            enriched = f"{working_transcript}\n\n[Prior semantic context: {ctx}]"
        if classification_note:
            enriched = f"{classification_note}\n\n{enriched}"

        try:
            print(f"[{call_id}] Claude: enriched re-classification with Moss context...")
            cls2 = await _run_sync_with_timeout(classify_threat, 20, enriched)
            return cls2, ctx
        except Exception as e:
            pipeline_errors.append("claude_enriched_classification")
            print(f"[{call_id}] WARNING: Enriched Claude classification failed: {e}")
            return classification, ctx

    async def _branch_parallel():
        """Geocode + Bayesian MC + Gemini verify + Supermemory — all at once."""
        print(f"[{call_id}] Parallel: Geocode + Bayesian + Gemini verify + Supermemory...")
        results = await asyncio.gather(
            # Geocode (skip if caller GPS already known)
            asyncio.to_thread(geolocate_school, school) if coords is None else asyncio.sleep(0, result=coords),
            # Bayesian Monte Carlo (500 sims — fast and still accurate)
            _run_sync_with_timeout(monte_carlo_score, 8, working_transcript, n_simulations=500),
            # Gemini second-opinion
            _run_sync_with_timeout(gemini_verify, 10, working_transcript, claude_level, call_id),
            # Supermemory prior tips
            _run_sync_with_timeout(
                search_prior_tips, 8, school,
                classification.get("threat_type", ""),
                classification.get("key_facts") or [],
            ),
            return_exceptions=True,
        )
        return results

    # Run both branches concurrently
    branch_results = await asyncio.gather(
        _branch_moss_claude(),
        _branch_parallel(),
        return_exceptions=True,
    )

    # Safe unpack branch A: _branch_moss_claude() returns (cls2, ctx) or an Exception
    branch_a = branch_results[0]
    if isinstance(branch_a, Exception):
        pipeline_errors.append("branch_moss_claude")
        print(f"[{call_id}] WARNING: moss+claude branch failed: {branch_a}")
        cls2 = classification
        moss_context = ""
    else:
        cls2, moss_context = branch_a

    # Safe unpack branch B: _branch_parallel() returns a list of 4 results or an Exception
    branch_b = branch_results[1]
    if isinstance(branch_b, Exception):
        pipeline_errors.append("branch_parallel")
        print(f"[{call_id}] WARNING: parallel branch failed: {branch_b}")
        parallel_results = [None, None, None, None]
    else:
        parallel_results = branch_b

    geo_res, bayes_res, gemini_res, prior_tips_res = parallel_results

    # ── Unpack geocode ────────────────────────────────────────────────────────
    if isinstance(geo_res, Exception):
        pipeline_errors.append("school_geocode")
        print(f"[{call_id}] WARNING: school geocode failed: {geo_res}")
        geo_res = coords  # fall back to caller GPS if any
    resolved_coords = geo_res if not isinstance(geo_res, Exception) else None

    # ── Unpack Bayesian ───────────────────────────────────────────────────────
    if isinstance(bayes_res, Exception):
        pipeline_errors.append("bayesian_score")
        print(f"[{call_id}] WARNING: Bayesian scoring failed: {bayes_res}")
        bayes_level = claude_level
        bayes_res = None
    else:
        bayes_level = probability_to_level(bayes_res["mean_probability"])
        cls2["bayes_probability_pct"] = bayes_res["mean_probability_pct"]
        cls2["bayes_ci_low_pct"]      = bayes_res["ci_low_pct"]
        cls2["bayes_ci_high_pct"]     = bayes_res["ci_high_pct"]
        cls2["bayes_top_drivers"]     = bayes_res["top_drivers"]
        cls2["bayes_features_hit"]    = bayes_res["features_hit"]
        print(
            f"[{call_id}] Bayesian: {bayes_res['mean_probability_pct']}% "
            f"[{bayes_res['ci_low_pct']}-{bayes_res['ci_high_pct']}% CI] "
            f"level {bayes_level}/5 | drivers: {[d['keyword'] for d in bayes_res['top_drivers']]}"
        )

    # ── Unpack Gemini verify ──────────────────────────────────────────────────
    if isinstance(gemini_res, Exception):
        pipeline_errors.append("gemini_verify")
        print(f"[{call_id}] WARNING: Gemini verify failed: {gemini_res}")
        gemini_res = {
            "gemini_level": claude_level,
            "gemini_reasoning": "Gemini unavailable; defaulted to Claude level.",
            "consensus": True,
        }
    else:
        try:
            disburse_agent_payment("gemini-verify", 3, call_id, {"school": school})
        except Exception as e:
            pipeline_errors.append("sponge_gemini_payment")
            print(f"[{call_id}] WARNING: Sponge Gemini payment failed: {e}")

    # ── Unpack Supermemory ────────────────────────────────────────────────────
    if isinstance(prior_tips_res, Exception):
        pipeline_errors.append("supermemory_search")
        print(f"[{call_id}] WARNING: Supermemory search failed: {prior_tips_res}")
        prior_tips = ""
    else:
        prior_tips = prior_tips_res or ""
        if prior_tips:
            try:
                disburse_agent_payment("supermemory-search", 1, call_id, {"school": school})
            except Exception as e:
                pipeline_errors.append("sponge_supermemory_payment")
                print(f"[{call_id}] WARNING: Sponge Supermemory payment failed: {e}")

    # ── Merge enriched classification into cls2 ───────────────────────────────
    if live_result.get("multilingual"):
        cls2.setdefault("caller_language", live_result.get("detected_language"))
        cls2.setdefault("multilingual_call", True)
        cls2.setdefault("english_translation", live_result.get("english_translation"))

    cls2["gemini_level"]      = gemini_res.get("gemini_level")
    cls2["gemini_reasoning"]  = gemini_res.get("gemini_reasoning")
    cls2["consensus"]         = gemini_res.get("consensus", False)
    cls2["caller_language"]   = live_result.get("detected_language")
    cls2["english_translation"] = live_result.get("english_translation")
    cls2["multilingual_call"] = live_result.get("multilingual", False)
    cls2["prior_tips_context"] = prior_tips
    cls2["call_duration_seconds"] = call_duration_seconds
    if deepgram_result:
        cls2["deepgram_confidence"] = deepgram_result.get("confidence")
        cls2["deepgram_language"]   = deepgram_result.get("language")

    gemini_l = gemini_res.get("gemini_level") or claude_level
    three_model_consensus = abs(claude_level - gemini_l) <= 1 and abs(claude_level - bayes_level) <= 1
    final_level = max(claude_level, gemini_l, bayes_level)
    cls2["three_model_consensus"] = three_model_consensus
    cls2["threat_level"] = final_level
    cls2["pipeline_errors"] = pipeline_errors

    if resolved_coords:
        cls2["call_lat"] = resolved_coords[0]
        cls2["call_lng"] = resolved_coords[1]
    location_context = _extract_location_context(cls2)
    if location_context:
        cls2["location_context"] = location_context

    # ── Extract and geocode any address mentioned in the transcript ──────────
    spoken_address = _extract_spoken_address(transcript)
    if spoken_address:
        print(f"[{call_id}] Spoken address detected: '{spoken_address}'")
        cls2["location_context"] = cls2.get("location_context") or spoken_address
        addr_coords = await asyncio.to_thread(_geocode_address, spoken_address, call_id)
        if addr_coords:
            cls2["mentioned_lat"] = addr_coords[0]
            cls2["mentioned_lng"] = addr_coords[1]
            # If no caller GPS was available, use mentioned address as the map pin
            if not resolved_coords:
                cls2["call_lat"] = addr_coords[0]
                cls2["call_lng"] = addr_coords[1]

    print(
        f"[{call_id}] 3-model: Claude={claude_level} Gemini={gemini_l} Bayes={bayes_level} "
        f"-> final={final_level} ({'CONSENSUS' if three_model_consensus else 'DIVERGENT'})"
    )

    # ── Supabase PATCH: update the early INSERT row with full enrichment ───────
    print(f"[{call_id}] Supabase: patching tip {tip_id} with enrichment data...")
    urgency_map  = {1:"low",2:"low",3:"medium",4:"high",5:"critical"}
    severity_map = {1:"low",2:"low",3:"medium",4:"high",5:"critical"}
    update_tip_enriched(tip_id, call_id, {
        "urgency":               urgency_map.get(final_level, "medium"),
        "severity":              severity_map.get(final_level, "medium"),
        "ai_triage_score":       final_level * 2,
        "ai_summary":            cls2.get("summary", ""),
        "ai_recommended_action": cls2.get("recommended_action", "monitor"),
        "school_name":           cls2.get("school_name"),
        "category":              cls2.get("threat_type", "other"),
        "gemini_level":          cls2.get("gemini_level"),
        "gemini_reasoning":      cls2.get("gemini_reasoning"),
        "consensus":             cls2.get("consensus"),
        "three_model_consensus": cls2.get("three_model_consensus"),
        "bayes_probability_pct": cls2.get("bayes_probability_pct"),
        "bayes_ci_low_pct":      cls2.get("bayes_ci_low_pct"),
        "bayes_ci_high_pct":     cls2.get("bayes_ci_high_pct"),
        "bayes_top_drivers":     cls2.get("bayes_top_drivers"),
        "bayes_features_hit":    cls2.get("bayes_features_hit"),
        "caller_language":       cls2.get("caller_language"),
        "english_translation":   cls2.get("english_translation"),
        "multilingual_call":     cls2.get("multilingual_call"),
        "prior_tips_context":    cls2.get("prior_tips_context"),
        "call_lat":              cls2.get("call_lat"),
        "call_lng":              cls2.get("call_lng"),
        "mentioned_lat":         cls2.get("mentioned_lat"),
        "mentioned_lng":         cls2.get("mentioned_lng"),
        "location_context":      cls2.get("location_context"),
        "pipeline_errors":       cls2.get("pipeline_errors"),
    })

    # Alias cls2 as classification for the rest of the pipeline
    classification = cls2

    # ── Post-dashboard tasks (fire-and-forget — don't block return) ───────────
    async def _post_dashboard_tasks():
        """OSINT, archive, SMS, email, Stripe — run after dashboard is already updated."""
        # pipeline_errors is a list (mutable) — mutated via .append(), no nonlocal needed

        # Attendance anomaly
        try:
            from attendance_anomaly import check_attendance_anomaly
            anomaly = check_attendance_anomaly(school, call_id)
            if anomaly.get("anomaly"):
                print(f"[{call_id}] ATTENDANCE ANOMALY: {anomaly['message']}")
                classification["attendance_anomaly"] = anomaly["message"]
        except Exception as e:
            pipeline_errors.append("attendance_anomaly")

        # Cross-school pattern
        cross_school_alert = None
        try:
            cross_school_alert = detect_cross_school_pattern(school, classification.get("threat_type", ""), call_id)
        except Exception as e:
            pipeline_errors.append("cross_school")
        if cross_school_alert:
            classification["cross_school_alert"] = cross_school_alert["message"]
            print(f"[{call_id}] CROSS-SCHOOL ALERT: {cross_school_alert['message'][:80]}")

        # Predictive threat window
        try:
            threat_window = predict_threat_window(working_transcript, classification)
            classification["threat_window"] = threat_window.get("window")
            classification["threat_window_confidence"] = threat_window.get("confidence")
        except Exception as e:
            pipeline_errors.append("threat_window")

        # Dispatch brief (level 4+)
        if final_level >= 4:
            try:
                brief = format_dispatch_brief(classification, call_id)
                classification["dispatch_brief"] = brief
                classification["location_context"] = classification.get("location_context") or _extract_location_context(classification)
                print(f"[{call_id}] Dispatch brief generated ({len(brief)} chars)")
            except Exception as e:
                pipeline_errors.append("dispatch_brief")

        # OSINT (level 3+)
        osint_summary = ""
        if final_level >= 3:
            # Prefer named_subject (actual full name) over subject_description (physical desc)
            named_subject = (
                classification.get("named_subject")
                or _extract_named_subject_from_transcript(transcript)
            )
            subject = (
                named_subject
                or classification.get("subject_description", "")
                or classification.get("school_name", "unknown subject")
            )
            print(f"[{call_id}] Background check subject: '{subject}' (named={bool(named_subject)})")
            bg_result = await asyncio.to_thread(
                run_paid_background_check,
                subject,
                school,
                call_id,
                final_level,
                classification.get("key_facts") or [],
            )
            classification["background_check"] = bg_result
            classification["background_check_subject"] = subject
            # Merge rich findings into osint_findings for display in modal
            findings = bg_result.get("findings", {})
            abstract = findings.get("abstract", "")
            risk = findings.get("risk_assessment", "")
            court_hits = findings.get("court_records", [])
            court_str = "; ".join(c.get("case_name", "") for c in court_hits[:2] if c.get("case_name"))
            bg_summary_parts = [p for p in [abstract, f"Courts: {court_str}" if court_str else "", risk] if p]
            classification["background_check_findings"] = f"Subject: {subject}. " + " | ".join(bg_summary_parts)
            print(f"[{call_id}] Background check: {abstract[:100]}")

            print(f"[{call_id}] Browser Use: OSINT search...")
            try:
                osint_summary = await asyncio.wait_for(
                    run_osint(
                        school,
                        classification.get("threat_type", ""),
                        classification.get("subject_description", ""),
                        named_subject=classification.get("background_check_subject", ""),
                    ),
                    timeout=15,
                )
            except Exception as e:
                pipeline_errors.append("osint")
                osint_summary = "OSINT unavailable"
            classification["osint_findings"] = osint_summary
            print(f"[{call_id}] OSINT: {osint_summary[:100]}")
            try:
                disburse_agent_payment("browser-use-osint", 2, call_id, {"school": school})
            except Exception:
                pass

        # AWS S3 archive
        try:
            s3_uri = await _run_sync_with_timeout(archive_transcript, 10, call_id, transcript, classification)
            if s3_uri:
                classification["s3_archive_uri"] = s3_uri
        except Exception as e:
            pipeline_errors.append("aws_archive")
            print(f"[{call_id}] WARNING: AWS archive failed: {e}")

        # Supermemory store
        try:
            await _run_sync_with_timeout(store_tip_memory, 5, classification, call_id)
        except Exception as e:
            pipeline_errors.append("supermemory_store")

        # Moss index
        try:
            index_tip(
                f"{school} {classification.get('threat_type','')} {classification.get('summary','')}",
                {"school": school, "level": final_level, "call_id": call_id},
                call_id,
            )
        except Exception as e:
            pipeline_errors.append("moss_index")

        # Patch final enrichment (OSINT, archive, dispatch brief) back to Supabase
        # Combine browser OSINT + DuckDuckGo background check findings
        osint_combined = classification.get("osint_findings") or ""
        bg_findings    = classification.get("background_check_findings") or ""
        if bg_findings and bg_findings not in osint_combined:
            osint_combined = (osint_combined + "\n\n[Background Check] " + bg_findings).strip()

        update_tip_enriched(tip_id, call_id, {
            "osint_findings":           osint_combined or None,
            "s3_archive_uri":           classification.get("s3_archive_uri"),
            "dispatch_brief":           classification.get("dispatch_brief"),
            "threat_window":            classification.get("threat_window"),
            "threat_window_confidence": classification.get("threat_window_confidence"),
            "cross_school_alert":       classification.get("cross_school_alert"),
            "pipeline_errors":          pipeline_errors,
            "background_check_subject": classification.get("background_check_subject"),
        })

        # Twilio SMS
        try:
            send_sms_alert(classification, call_id)
            disburse_agent_payment("twilio-sms", 1, call_id, {"school": school})
        except Exception as e:
            pipeline_errors.append("sms_alert")
            print(f"[{call_id}] SMS error: {e}")

        # AgentMail email
        try:
            tip_data = {
                **classification,
                "call_id": call_id,
                "timestamp": datetime.utcnow().isoformat(),
                "transcript": transcript,
            }
            subject, body = generate_email_brief(tip_data)
            send_email_brief(subject, body, call_id, classification=classification)
            disburse_agent_payment("agentmail-brief", 1, call_id, {"school": school})
        except Exception as e:
            pipeline_errors.append("email_brief")
            print(f"[{call_id}] Email error: {e}")

        # Stripe billing
        try:
            charge_for_tip(classification, call_id)
        except Exception as e:
            pipeline_errors.append("stripe")
            print(f"[{call_id}] Stripe error: {e}")

        enrichment_count = sum(1 for s in [osint_summary, prior_tips, moss_context, gemini_res.get("gemini_level")] if s)
        print(f"[{call_id}] ✓ Post-processing complete — {enrichment_count} enrichment sources")

    # Fire background tasks without blocking the return
    asyncio.create_task(_post_dashboard_tasks())

    enrichment_count = sum(1 for s in [prior_tips, moss_context, gemini_res.get("gemini_level")] if s)
    print(f"[{call_id}] ✓ Core pipeline complete — level {final_level}/5, tip on dashboard (id: {tip_id})")
    return classification
