import anthropic
import json
import os
import re
import time
from datetime import date, timedelta
from prompts import CLASSIFICATION_PROMPT, EMAIL_BRIEF_PROMPT

_client = None

ATTENDANCE_KEYWORDS = (
    "absent", "absence", "sick", "ill", "fever", "doctor", "dentist",
    "appointment", "not coming", "won't be in", "will not be in",
    "staying home", "miss school", "miss class", "out today"
)
THREAT_KEYWORDS = (
    "gun", "weapon", "knife", "bomb", "shoot", "kill", "hurt",
    "threat", "fight", "attack", "suicide", "self harm", "drugs"
)

def _get_langfuse():
    try:
        from langfuse import Langfuse
        pk = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        sk = os.getenv("LANGFUSE_SECRET_KEY", "")
        if not pk or not sk or pk == "FILL_IN":
            return None
        return Langfuse(public_key=pk, secret_key=sk)
    except ImportError:
        return None

def _get_client():
    global _client
    if _client is None:
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key or key == "FILL_IN":
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _client = anthropic.Anthropic(api_key=key)
    return _client

def _looks_like_attendance(transcript: str) -> bool:
    text = transcript.lower()
    return any(k in text for k in ATTENDANCE_KEYWORDS) and not any(k in text for k in THREAT_KEYWORDS)

def _extract_attendance(transcript: str) -> dict:
    text = transcript.strip()
    lower = text.lower()

    student_name = None
    student_patterns = [
        r"\b(?:my son|my daughter|my child|student)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:is|will be|won't be|will not be)\s+(?:absent|out|sick)",
        r"\bcalling (?:for|about)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    ]
    for pattern in student_patterns:
        match = re.search(pattern, text)
        if match:
            student_name = match.group(1).strip()
            break

    teacher_name = None
    teacher_match = re.search(r"\b(?:mrs?\.?|ms\.?|miss|teacher)\s+([A-Z][a-z]+)", text, re.IGNORECASE)
    if teacher_match:
        teacher_name = teacher_match.group(1).strip()
        prefix_match = re.search(r"\b(Mrs?\.?|Ms\.?|Miss)\s+" + re.escape(teacher_name), text, re.IGNORECASE)
        if prefix_match:
            teacher_name = f"{prefix_match.group(1).rstrip('.')}. {teacher_name}"

    grade = None
    grade_match = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:grade|period|class)\b", lower)
    if grade_match:
        grade = grade_match.group(0)

    absence_date = date.today().isoformat()
    if "tomorrow" in lower:
        absence_date = (date.today() + timedelta(days=1)).isoformat()
    elif "yesterday" in lower:
        absence_date = (date.today() - timedelta(days=1)).isoformat()

    reason = "Not specified"
    reason_patterns = [
        r"\b(?:because|since|as)\s+(.+?)(?:\.|$)",
        r"\b(?:he's|she's|they're|he is|she is|they are)\s+(.+?)(?:\.|$)",
    ]
    for pattern in reason_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            candidate_l = candidate.lower()
            if candidate and "class" not in candidate_l and not candidate_l.startswith(("in ", "with ")):
                reason = candidate
                break

    return {
        "call_type": "attendance",
        "threat_level": 1,
        "threat_type": "attendance",
        "summary": "Attendance report received.",
        "school_name": None,
        "student_name": student_name,
        "teacher_name": teacher_name,
        "grade": grade,
        "absence_date": absence_date,
        "reason": reason,
        "recommended_action": "log_attendance",
    }

def classify_threat(transcript: str) -> dict:
    if _looks_like_attendance(transcript):
        return _extract_attendance(transcript)

    lf = _get_langfuse()
    trace = lf.trace(name="threat-classification") if lf else None
    span = trace.span(name="claude-classify") if trace else None

    t0 = time.time()
    prompt = CLASSIFICATION_PROMPT.format(transcript=transcript) + """

Also classify the call_type:
- "attendance" for routine absence reporting
- "threat" for safety, violence, self-harm, weapons, bullying, drugs, or emergency tips
- "general" for other school calls that are neither attendance nor safety tips

Return call_type as a top-level JSON field.
If call_type is "attendance", include student_name, teacher_name, grade, absence_date, and reason when available.
"""
    message = _get_client().messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    latency_ms = int((time.time() - t0) * 1000)

    text = message.content[0].text.strip()
    result = {}
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        result = json.loads(match.group()) if match else {}

    if span:
        span.end(
            output=result,
            metadata={
                "latency_ms": latency_ms,
                "threat_level": result.get("threat_level"),
                "model": "claude-opus-4-5",
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            }
        )
    result.setdefault("call_type", "threat")
    return result

def generate_email_brief(tip_data: dict) -> tuple[str, str]:
    prompt = EMAIL_BRIEF_PROMPT.format(tip_data=json.dumps(tip_data, indent=2))
    message = _get_client().messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    text = message.content[0].text.strip()
    lines = text.split("\n")
    subject = ""
    body_lines = []
    for line in lines:
        if line.startswith("SUBJECT:"):
            subject = line.replace("SUBJECT:", "").strip()
        else:
            body_lines.append(line)
    return subject, "\n".join(body_lines).strip()
