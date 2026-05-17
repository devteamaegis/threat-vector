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
from datetime import datetime

async def run_threat_agent(call_id: str, transcript: str, recording_url: str | None = None):
    print(f"[{call_id}] Starting threat agent pipeline...")

    deepgram_result = {}
    if recording_url:
        print(f"[{call_id}] Deepgram: re-transcribing call recording...")
        deepgram_result = transcribe_audio_url(recording_url, call_id)
        if deepgram_result.get("confidence", 0) > 0.85 and deepgram_result.get("transcript"):
            transcript = deepgram_result["transcript"]
            print(f"[{call_id}] Deepgram: using transcript with {deepgram_result['confidence']:.2f} confidence")

    # ── Gemini Live: multilingual detection + real-time translation ───────────
    # Runs FIRST — if non-English, Claude receives the English translation.
    # This means any of 70 languages works end-to-end automatically.
    print(f"[{call_id}] Gemini Live: multilingual real-time analysis...")
    live_result = await live_multilingual_analysis(transcript, call_id)
    if live_result.get("multilingual") and live_result.get("english_translation"):
        lang = live_result["detected_language"]
        print(f"[{call_id}] Non-English call detected: {lang} — using translation for Claude")
        # Use the translated transcript for all downstream processing
        working_transcript = live_result["english_translation"]
        classification_note = f"[Original language: {lang}. Auto-translated by Gemini Live.]"
    else:
        working_transcript = transcript
        classification_note = ""

    # ── Moss: semantic context search before classification ───────────────────
    print(f"[{call_id}] Moss: semantic context search...")
    moss_context = semantic_search_tips(working_transcript[:300], call_id)
    if moss_context:
        print(f"[{call_id}] Moss context: {moss_context[:80]}...")

    # ── Claude: classify threat (Moss context injected) ───────────────────────
    print(f"[{call_id}] Claude: classifying threat...")
    enriched_transcript = working_transcript
    if moss_context:
        enriched_transcript = f"{working_transcript}\n\n[Prior semantic context: {moss_context}]"
    if classification_note:
        enriched_transcript = f"{classification_note}\n\n{enriched_transcript}"
    classification = classify_threat(enriched_transcript)
    claude_level = classification.get("threat_level", 3)
    school = classification.get("school_name", "Unknown School")
    print(f"[{call_id}] Claude: level {claude_level}/5, school: {school}")

    # ── Google DeepMind: Gemini second-opinion verification ───────────────────
    print(f"[{call_id}] Gemini: independent threat verification...")
    gemini_result = gemini_verify(working_transcript, claude_level, call_id)
    classification["gemini_level"] = gemini_result.get("gemini_level")
    classification["gemini_reasoning"] = gemini_result.get("gemini_reasoning")
    classification["consensus"] = gemini_result.get("consensus", False)
    # Multilingual metadata from Gemini Live
    classification["caller_language"] = live_result.get("detected_language")
    classification["english_translation"] = live_result.get("english_translation")
    classification["multilingual_call"] = live_result.get("multilingual", False)
    if deepgram_result:
        classification["deepgram_confidence"] = deepgram_result.get("confidence")
        classification["deepgram_language"] = deepgram_result.get("language")
    # Use consensus level as the final threat level
    final_level = gemini_result.get("consensus_level", claude_level)
    classification["threat_level"] = final_level

    # ── Supermemory: prior tips context ───────────────────────────────────────
    print(f"[{call_id}] Supermemory: checking prior tips...")
    prior_tips = search_prior_tips(school)
    classification["prior_tips_context"] = prior_tips

    # ── Browser Use: OSINT (level 3+) ─────────────────────────────────────────
    osint_summary = ""
    if final_level >= 3:
        print(f"[{call_id}] Browser Use: OSINT search...")
        osint_summary = await run_osint(
            school,
            classification.get("threat_type", ""),
            classification.get("subject_description", "")
        )
        classification["osint_findings"] = osint_summary
        print(f"[{call_id}] OSINT: {osint_summary[:100]}")
        disburse_agent_payment("browser-use-osint", 2, call_id, {"school": school})

    # ── Supabase: log to Threat Vector dashboard ──────────────────────────────
    print(f"[{call_id}] Supabase: logging to dashboard...")
    tip_id = log_tip_to_aegis(classification, transcript, call_id, osint_summary)
    print(f"[{call_id}] Supabase: tip ID {tip_id}")

    # ── AWS S3: archive transcript + report ───────────────────────────────────
    print(f"[{call_id}] AWS S3: archiving transcript...")
    s3_uri = archive_transcript(call_id, transcript, classification)
    if s3_uri:
        classification["s3_archive_uri"] = s3_uri

    # ── Supermemory: store for future pattern matching ────────────────────────
    print(f"[{call_id}] Supermemory: storing tip memory...")
    store_tip_memory(classification, call_id)

    # ── Moss: index tip for future semantic search ────────────────────────────
    index_tip(
        f"{school} {classification.get('threat_type','')} {classification.get('summary','')}",
        {"school": school, "level": final_level, "call_id": call_id},
        call_id
    )

    # ── Twilio: SMS to principal ──────────────────────────────────────────────
    print(f"[{call_id}] Twilio: sending SMS alert...")
    try:
        send_sms_alert(classification, call_id)
        disburse_agent_payment("twilio-sms", 1, call_id, {"school": school})
    except Exception as e:
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
        send_email_brief(subject, body, call_id)
        disburse_agent_payment("agentmail-brief", 1, call_id, {"school": school})
    except Exception as e:
        print(f"[{call_id}] Email error: {e}")

    # ── Stripe: bill district for tip processing ──────────────────────────────
    print(f"[{call_id}] Stripe: billing district...")
    charge_for_tip(classification, call_id)

    enrichment_count = sum(1 for s in [osint_summary, prior_tips, moss_context, gemini_result.get("gemini_level")] if s)
    print(f"[{call_id}] ✓ Pipeline complete — level {final_level}/5, {enrichment_count} enrichment sources")
    return classification
