"""
Formats a 911-ready dispatch brief from a threat classification.
Used for Level 4-5 threats.

The brief is a natural-language paragraph ready to be read verbatim to
911 dispatch or a school safety officer.
"""
from datetime import datetime, timezone


def format_dispatch_brief(classification: dict, call_id: str) -> str:
    """
    Return a formatted dispatch brief string ready to read to 911 dispatch.

    Fills in whatever fields are available from classification; skips gracefully
    if a field is missing.

    Args:
        classification: The threat classification dict produced by agent.py
        call_id: The unique call identifier (used as fallback tip ID)

    Returns:
        A multi-sentence dispatch brief string.
    """
    # ── Extract fields ────────────────────────────────────────────────────────
    school = classification.get("school_name") or "Unknown School"
    threat_type = classification.get("threat_type") or classification.get("category") or "unspecified threat"
    location = classification.get("location_detail") or "campus"
    subject = classification.get("subject_description") or ""
    ai_summary = classification.get("ai_summary") or ""
    threat_level = classification.get("threat_level") or 0
    urgency = (classification.get("urgency") or "").upper() or _level_to_urgency(threat_level)
    bayes_pct = classification.get("bayes_probability_pct")
    three_model = classification.get("three_model_consensus", False)
    recommended_action = (
        classification.get("ai_recommended_action") or "immediate_response"
    ).replace("_", " ").title()
    tip_id = classification.get("tip_id") or call_id
    threat_window = classification.get("threat_window") or ""
    timeline_raw = classification.get("timeline") or ""

    # Determine timeline string for brief
    timeline_str = threat_window or timeline_raw or "unknown"

    # Truncate AI summary for readability
    if ai_summary and len(ai_summary) > 150:
        ai_summary = ai_summary[:147].rstrip() + "…"

    # Confidence string
    if bayes_pct is not None:
        confidence_str = f"{bayes_pct}% ({'3-model consensus' if three_model else 'single model'})"
    else:
        confidence_str = "unavailable"

    # ── Build timestamp ───────────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%B %d, %Y")
    time_str = now.strftime("%H:%M UTC")

    # ── Compose brief ─────────────────────────────────────────────────────────
    lines: list[str] = []

    lines.append(f"PRIORITY THREAT ALERT — {school}, {date_str}.")
    lines.append("")

    # Sentence 1: tip received
    lines.append(f"Anonymous tip received at {time_str}.")

    # Sentence 2: threat description
    threat_sentence = f"Reported threat: {threat_type} at {location}."
    if subject:
        threat_sentence += f" {subject}."
    lines.append(threat_sentence)

    # Sentence 3: caller summary
    if ai_summary:
        lines.append(f"Caller reported: {ai_summary}")

    # Sentence 4: timeline
    lines.append(f"Threat timeline: {timeline_str}.")

    # Sentence 5: level and confidence
    lines.append(
        f"Threat level: {threat_level}/5 ({urgency}). AI confidence: {confidence_str}."
    )

    lines.append("")

    # Sentence 6: recommended action
    lines.append(f"Recommended action: {recommended_action}.")

    # Sentence 7: log reference
    lines.append(
        f"This report has been logged to Supabase (ID: {tip_id})."
    )

    return "\n".join(lines)


def _level_to_urgency(level: int) -> str:
    """Map numeric threat level to urgency label."""
    mapping = {5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "INFORMATIONAL"}
    return mapping.get(level, "UNKNOWN")
