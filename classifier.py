import anthropic
import json
import os
import time
from prompts import CLASSIFICATION_PROMPT, EMAIL_BRIEF_PROMPT

_client = None

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

def classify_threat(transcript: str) -> dict:
    lf = _get_langfuse()
    trace = lf.trace(name="threat-classification") if lf else None
    span = trace.span(name="claude-classify") if trace else None

    t0 = time.time()
    prompt = CLASSIFICATION_PROMPT.format(transcript=transcript)
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
