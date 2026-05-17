import anthropic
import json
import os
from prompts import CLASSIFICATION_PROMPT, EMAIL_BRIEF_PROMPT

_client = None

def _get_client():
    global _client
    if _client is None:
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key or key == "FILL_IN":
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _client = anthropic.Anthropic(api_key=key)
    return _client

def classify_threat(transcript: str) -> dict:
    prompt = CLASSIFICATION_PROMPT.format(transcript=transcript)
    message = _get_client().messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    text = message.content[0].text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(match.group()) if match else {}

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
