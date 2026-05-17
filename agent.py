import asyncio
from classifier import classify_threat, generate_email_brief
from osint import run_osint
from notify import send_sms_alert, send_email_brief
from memory import store_tip_memory, search_prior_tips
from supabase import log_tip_to_aegis
from moss_search import semantic_search_tips, index_tip
from stripe_billing import charge_for_tip
from sponge_payments import disburse_agent_payment
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

async def _run_sync_with_timeout(func, timeout: int, *args, **kwargs):
    return await asyncio.wait_for(asyncio.to_thread(func, *args, **kwargs), timeout=timeout)

async def run_threat_agent(call_id: str, transcript: str, recording_url: str | None = None):
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

    # First classify the call type. Attendance calls end here after logging.
    try:
        classification = await _run_sync_with_timeout(classify_threat, 20, transcript)
    except Exception as e:
        pipeline_errors.append("claude_classification")
        print(f"[{call_id}] WARNING: Claude classification failed: {e}")
        classification = {
            "call_type": "general",
            "threat_level": 3,
            "threat_type": "other",
            "summary": transcript[:240],
            "school_name": "Unknown School",
            "recommended_action": "manual_review",
        }

    classification["pipeline_errors"] = pipeline_errors

    if classification.get("call_type") == "attendance":
        print(f"[{call_id}] Attendance call detected — skipping threat pipeline")
        log_attendance(classification, call_id)
        return classification

    # ── Gemini Live: multilingual detection + real-time translation ───────────
    print(f"[{call_id}] Gemini Live: multilingual real-time analysis...")
    try:
        live_result = await asyncio.wait_for(live_multilingual_analysis(transcript, call_id), timeout=10)
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
        print(f"[{call_id}] Non-English call detected: {lang} — using translation for Claude")
        working_transcript = live_result["english_translation"]
        classification_note = f"[Original language: {lang}. Auto-translated by Gemini Live.]"
    else:
        working_transcript = transcript
        classification_note = ""

    # ── Moss: semantic context search before final threat classification ──────
    print(f"[{call_id}] Moss: semantic context search...")
    try:
        moss_context = await _run_sync_with_timeout(semantic_search_tips, 5, working_transcript[:300], call_id)
    except Exception as e:
        pipeline_errors.append("moss_search")
        print(f"[{call_id}] WARNING: Moss search failed: {e}")
        moss_context = ""
    if moss_context:
        print(f"[{call_id}] Moss context: {moss_context[:80]}...")

    # ── Claude: re-classify threat with Moss context injected ─────────────────
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

    classification["pipeline_errors"] = pipeline_errors
    claude_level = classification.get("threat_level", 3)
    school = classification.get("school_name", "Unknown School")
    print(f"[{call_id}] Claude: level {claude_level}/5, school: {school}")

    # ── Bayesian + Monte Carlo scoring ───────────────────────────────────────
    print(f"[{call_id}] Bayesian/MC: scoring verbal context clues...")
    try:
        bayes = await _run_sync_with_timeout(monte_carlo_score, 8, working_transcript, n_simulations=1000)
        bayes_level = probability_to_level(bayes["mean_probability"])
        classification["bayes_probability_pct"] = bayes["mean_probability_pct"]
        classification["bayes_ci_low_pct"]      = bayes["ci_low_pct"]
        classification["bayes_ci_high_pct"]     = bayes["ci_high_pct"]
        classification["bayes_top_drivers"]     = bayes["top_drivers"]
        classification["bayes_features_hit"]    = bayes["features_hit"]
        print(
            f"[{call_id}] Bayesian: {bayes['mean_probability_pct']}% "
            f"[{bayes['ci_low_pct']}-{bayes['ci_high_pct']}% CI] "
            f"level {bayes_level}/5 | drivers: {[d['keyword'] for d in bayes['top_drivers']]}"
        )
    except Exception as e:
        pipeline_errors.append("bayesian_score")
        print(f"[{call_id}] WARNING: Bayesian scoring failed: {e}")
        bayes_level = claude_level

    # ── Google DeepMind: Gemini second-opinion verification ───────────────────
    print(f"[{call_id}] Gemini: independent threat verification...")
    try:
        gemini_result = await _run_sync_with_timeout(gemini_verify, 8, working_transcript, claude_level, call_id)
        try:
            disburse_agent_payment("gemini-verify", 3, call_id, {"school": school})
        except Exception as e:
            pipeline_errors.append("sponge_gemini_payment")
            print(f"[{call_id}] WARNING: Sponge Gemini payment failed: {e}")
    except Exception as e:
        pipeline_errors.append("gemini_verify")
        print(f"[{call_id}] WARNING: Gemini verify failed: {e}")
        gemini_result = {
            "gemini_level": claude_level,
            "gemini_reasoning": "Gemini unavailable; defaulted to Claude level.",
            "consensus": True,
            "consensus_level": claude_level,
        }

    classification["gemini_level"] = gemini_result.get("gemini_level")
    classification["gemini_reasoning"] = gemini_result.get("gemini_reasoning")
    classification["consensus"] = gemini_result.get("consensus", False)
    classification["caller_language"] = live_result.get("detected_language")
    classification["english_translation"] = live_result.get("english_translation")
    classification["multilingual_call"] = live_result.get("multilingual", False)
    if deepgram_result:
        classification["deepgram_confidence"] = deepgram_result.get("confidence")
        classification["deepgram_language"] = deepgram_result.get("language")

    gemini_l = gemini_result.get("gemini_level") or claude_level
    three_model_consensus = abs(claude_level - gemini_l) <= 1 and abs(claude_level - bayes_level) <= 1
    final_level = max(claude_level, gemini_l, bayes_level)
    classification["three_model_consensus"] = three_model_consensus
    classification["threat_level"] = final_level
    print(
        f"[{call_id}] 3-model: Claude={claude_level} Gemini={gemini_l} Bayes={bayes_level} "
        f"-> final={final_level} ({'CONSENSUS' if three_model_consensus else 'DIVERGENT'})"
    )

    # ── Supermemory: multi-dimensional prior tips context ─────────────────────
    print(f"[{call_id}] Supermemory: checking prior tips (school + type + behavioral)...")
    try:
        prior_tips = await _run_sync_with_timeout(
            search_prior_tips, 8, school,
            classification.get("threat_type", ""),
            classification.get("key_facts") or [],
        )
    except Exception as e:
        pipeline_errors.append("supermemory_search")
        print(f"[{call_id}] WARNING: Supermemory search failed: {e}")
        prior_tips = ""
    classification["prior_tips_context"] = prior_tips
    if prior_tips:
        try:
            disburse_agent_payment("supermemory-search", 1, call_id, {"school": school})
        except Exception as e:
            pipeline_errors.append("sponge_supermemory_payment")
            print(f"[{call_id}] WARNING: Sponge Supermemory payment failed: {e}")

    # ── Browser Use: OSINT (level 3+) ─────────────────────────────────────────
    osint_summary = ""
    if final_level >= 3:
        print(f"[{call_id}] Browser Use: OSINT search...")
        try:
            osint_summary = await asyncio.wait_for(
                run_osint(
                    school,
                    classification.get("threat_type", ""),
                    classification.get("subject_description", "")
                ),
                timeout=15,
            )
        except Exception as e:
            pipeline_errors.append("osint")
            print(f"[{call_id}] WARNING: OSINT failed: {e}")
            osint_summary = "OSINT unavailable"
        classification["osint_findings"] = osint_summary
        print(f"[{call_id}] OSINT: {osint_summary[:100]}")
        try:
            disburse_agent_payment("browser-use-osint", 2, call_id, {"school": school})
        except Exception as e:
            pipeline_errors.append("sponge_osint_payment")
            print(f"[{call_id}] WARNING: Sponge OSINT payment failed: {e}")

    # ── Supabase: log to Threat Vector dashboard ──────────────────────────────
    print(f"[{call_id}] Supabase: logging to dashboard...")
    tip_id = log_tip_to_aegis(classification, transcript, call_id, osint_summary)
    print(f"[{call_id}] Supabase: tip ID {tip_id}")

    # ── Cross-school pattern detection ────────────────────────────────────────
    print(f"[{call_id}] Cross-school: checking for coordinated threat patterns...")
    try:
        cross_school_alert = detect_cross_school_pattern(school, classification.get("threat_type", ""), call_id)
    except Exception as e:
        pipeline_errors.append("cross_school")
        print(f"[{call_id}] WARNING: Cross-school detection failed: {e}")
        cross_school_alert = None
    if cross_school_alert:
        classification["cross_school_alert"] = cross_school_alert["message"]
        print(f"[{call_id}] CROSS-SCHOOL ALERT: {cross_school_alert['message'][:80]}")

    # ── Predictive threat window ──────────────────────────────────────────────
    try:
        threat_window = predict_threat_window(working_transcript, classification)
        classification["threat_window"] = threat_window.get("window")
        classification["threat_window_confidence"] = threat_window.get("confidence")
        print(f"[{call_id}] Threat window: {threat_window.get('window')} ({threat_window.get('confidence')} confidence)")
    except Exception as e:
        pipeline_errors.append("threat_window")
        print(f"[{call_id}] WARNING: Threat window failed: {e}")

    # ── Dispatch brief (level 4+) ─────────────────────────────────────────────
    if final_level >= 4:
        try:
            brief = format_dispatch_brief(classification, call_id)
            classification["dispatch_brief"] = brief
            print(f"[{call_id}] Dispatch brief generated ({len(brief)} chars)")
        except Exception as e:
            pipeline_errors.append("dispatch_brief")
            print(f"[{call_id}] WARNING: Dispatch brief failed: {e}")

    # ── AWS S3: archive transcript + report ───────────────────────────────────
    print(f"[{call_id}] AWS S3: archiving transcript...")
    try:
        s3_uri = await _run_sync_with_timeout(archive_transcript, 10, call_id, transcript, classification)
    except Exception as e:
        pipeline_errors.append("aws_archive")
        print(f"[{call_id}] WARNING: AWS archive failed: {e}")
        s3_uri = None
    if s3_uri:
        classification["s3_archive_uri"] = s3_uri

    # ── Supermemory: store for future pattern matching ────────────────────────
    print(f"[{call_id}] Supermemory: storing tip memory...")
    try:
        await _run_sync_with_timeout(store_tip_memory, 5, classification, call_id)
    except Exception as e:
        pipeline_errors.append("supermemory_store")
        print(f"[{call_id}] WARNING: Supermemory store failed: {e}")

    # ── Moss: index tip for future semantic search ────────────────────────────
    try:
        index_tip(
            f"{school} {classification.get('threat_type','')} {classification.get('summary','')}",
            {"school": school, "level": final_level, "call_id": call_id},
            call_id
        )
    except Exception as e:
        pipeline_errors.append("moss_index")
        print(f"[{call_id}] WARNING: Moss index failed: {e}")

    # ── Twilio: SMS to principal ──────────────────────────────────────────────
    print(f"[{call_id}] Twilio: sending SMS alert...")
    try:
        send_sms_alert(classification, call_id)
        disburse_agent_payment("twilio-sms", 1, call_id, {"school": school})
    except Exception as e:
        pipeline_errors.append("sms_alert")
        print(f"[{call_id}] SMS error: {e}")

    # ── AgentMail: email brief to safety officer ──────────────────────────────
    print(f"[{call_id}] AgentMail: sending threat brief email...")
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

    # ── Stripe: bill district for tip processing ──────────────────────────────
    print(f"[{call_id}] Stripe: billing district...")
    try:
        charge_for_tip(classification, call_id)
    except Exception as e:
        pipeline_errors.append("stripe")
        print(f"[{call_id}] Stripe error: {e}")

    classification["pipeline_errors"] = pipeline_errors
    enrichment_count = sum(1 for s in [osint_summary, prior_tips, moss_context, gemini_result.get("gemini_level")] if s)
    print(f"[{call_id}] ✓ Pipeline complete — level {final_level}/5, {enrichment_count} enrichment sources")
    return classification
