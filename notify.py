import os
import requests
from datetime import datetime

THREAT_LEVEL_LABELS = {1: "LOW", 2: "LOW-MEDIUM", 3: "MEDIUM", 4: "HIGH", 5: "CRITICAL"}
AGENTMAIL_BASE = "https://api.agentmail.to"


def send_sms_alert(classification: dict, call_id: str):
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_num = os.getenv("TWILIO_FROM_NUMBER")
    to_num = os.getenv("PRINCIPAL_PHONE")

    if not all([sid, token, from_num, to_num]) or "FILL_IN" in (sid or "") or "+1XXXXXXXXXX" in (to_num or ""):
        print(f"[{call_id}] WARNING: Twilio credentials not set — skipping SMS")
        return False

    from twilio.rest import Client
    level = classification.get("threat_level", 3)
    label = THREAT_LEVEL_LABELS.get(level, "UNKNOWN")
    school = classification.get("school_name", "Unknown school")
    action = classification.get("recommended_action", "review")
    summary = classification.get("summary", "No summary available.")

    body = (
        f"[THREAT VECTOR ALERT] Level {level}/5 ({label})\n"
        f"School: {school}\n"
        f"Action: {action.upper().replace('_', ' ')}\n"
        f"{summary}\n"
        f"Full brief sent to safety officer email. Log ID: {call_id[:8]}"
    )

    try:
        client = Client(sid, token)
        client.messages.create(body=body, from_=from_num, to=to_num)
        return True
    except Exception as e:
        print(f"[{call_id}] WARNING: SMS send failed: {e}")
        return False


def send_email_brief(subject: str, body: str, call_id: str):
    """
    Send threat brief via AgentMail.
    Endpoint: POST /v0/inboxes/{inbox_id}/messages/send
    AGENTMAIL_INBOX_ID = the inbox identifier (from AgentMail dashboard)
    AGENTMAIL_FROM     = the sender email address (your AgentMail inbox address)
    """
    api_key = os.getenv("AGENTMAIL_API_KEY")
    inbox_id = os.getenv("AGENTMAIL_INBOX_ID")
    from_addr = os.getenv("AGENTMAIL_FROM", os.getenv("AGENTMAIL_INBOX", ""))
    recipient = os.getenv("SAFETY_OFFICER_EMAIL")

    if not api_key or api_key == "FILL_IN":
        print(f"[{call_id}] WARNING: AGENTMAIL_API_KEY not set — skipping email")
        return False

    if not inbox_id or inbox_id == "FILL_IN":
        print(f"[{call_id}] WARNING: AGENTMAIL_INBOX_ID not set — skipping email")
        return False

    if not recipient:
        print(f"[{call_id}] WARNING: SAFETY_OFFICER_EMAIL not set — skipping email")
        return False

    url = f"{AGENTMAIL_BASE}/v0/inboxes/{inbox_id}/messages/send"

    payload = {
        "to": recipient,
        "subject": subject or f"[Threat Vector] Threat Report — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
        "text": body,
    }
    if from_addr and from_addr not in ("FILL_IN", "threats@your-inbox.agentmail.to"):
        payload["reply_to"] = from_addr

    try:
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=12,
        )
        if r.status_code in (200, 201):
            print(f"[{call_id}] AgentMail: email sent to {recipient}")
            return True
        print(f"[{call_id}] WARNING: AgentMail returned {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"[{call_id}] WARNING: AgentMail send failed: {e}")
        return False
