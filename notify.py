import os
import requests
from datetime import datetime

THREAT_LEVEL_LABELS = {1: "LOW", 2: "LOW-MEDIUM", 3: "MEDIUM", 4: "HIGH", 5: "CRITICAL"}
URGENCY_COLORS = {1: "#6b7280", 2: "#3b82f6", 3: "#f59e0b", 4: "#f97316", 5: "#dc2626"}
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
    window = classification.get("threat_window", "")
    brief = classification.get("dispatch_brief", "")

    body = (
        f"[THREAT VECTOR] Level {level}/5 — {label}\n"
        f"School: {school}\n"
        f"Action: {action.upper().replace('_', ' ')}\n"
        + (f"Window: {window}\n" if window else "")
        + f"{summary[:160]}\n"
        + (f"\n911 Brief: {brief[:120]}" if brief else "")
        + f"\nFull report in email. ID: {call_id[:8]}"
    )

    try:
        client = Client(sid, token)
        client.messages.create(body=body, from_=from_num, to=to_num)
        print(f"[{call_id}] Twilio: SMS sent to principal")
        return True
    except Exception as e:
        print(f"[{call_id}] WARNING: SMS send failed: {e}")
        return False


def _build_html_email(classification: dict, call_id: str, timestamp: str) -> str:
    level = classification.get("threat_level", 3)
    label = THREAT_LEVEL_LABELS.get(level, "UNKNOWN")
    color = URGENCY_COLORS.get(level, "#6b7280")
    school = classification.get("school_name", "Unknown")
    category = (classification.get("threat_type") or "unknown").replace("_", " ").title()
    summary = classification.get("summary", "")
    action = (classification.get("recommended_action") or "review").replace("_", " ").upper()
    window = classification.get("threat_window", "")
    brief = classification.get("dispatch_brief", "")
    facts = classification.get("key_facts") or []
    credibility = classification.get("credibility_signals") or []
    emotion = classification.get("caller_emotion", "")
    escalation = classification.get("escalation_risk", "")
    bayes_pct = classification.get("bayes_probability_pct", "")
    bayes_drivers = classification.get("bayes_top_drivers") or []
    claude_level = classification.get("threat_level", level)
    gemini_level = classification.get("gemini_level", "—")
    consensus = classification.get("three_model_consensus", False)
    prior_context = classification.get("prior_tips_context", "")
    osint = classification.get("osint_findings", "")
    cross_school = classification.get("cross_school_alert", "")

    facts_html = "".join(f"<li style='margin:4px 0;color:#374151'>{f}</li>" for f in facts[:6])
    cred_html = "".join(f"<li style='margin:4px 0;color:#374151'>{c}</li>" for c in credibility[:4])
    drivers_html = "".join(f"<li style='margin:4px 0;color:#374151'>{d}</li>" for d in bayes_drivers[:5])

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Threat Vector Report</title></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f4f4f5">
<div style="max-width:700px;margin:24px auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.10)">

  <!-- Urgency Banner -->
  <div style="background:{color};padding:24px 32px">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div>
        <div style="color:rgba(255,255,255,0.85);font-size:11px;font-weight:600;letter-spacing:1.5px;text-transform:uppercase">THREAT VECTOR ALERT</div>
        <div style="color:#ffffff;font-size:28px;font-weight:800;margin-top:4px">Level {level}/5 — {label}</div>
        <div style="color:rgba(255,255,255,0.9);font-size:15px;margin-top:6px">{school} · {category}</div>
      </div>
      <div style="text-align:right">
        <div style="background:rgba(0,0,0,0.2);border-radius:8px;padding:12px 16px;color:#fff">
          <div style="font-size:11px;opacity:0.8">REQUIRED ACTION</div>
          <div style="font-size:16px;font-weight:700;margin-top:2px">{action}</div>
        </div>
      </div>
    </div>
  </div>

  <!-- Summary -->
  <div style="padding:24px 32px;border-bottom:1px solid #e5e7eb">
    <div style="font-size:11px;font-weight:600;letter-spacing:1px;color:#9ca3af;text-transform:uppercase;margin-bottom:8px">AI SUMMARY</div>
    <div style="font-size:15px;color:#111827;line-height:1.6">{summary}</div>
    {f'<div style="margin-top:12px;padding:10px 14px;background:#fef3c7;border-left:3px solid #f59e0b;border-radius:4px;font-size:13px;color:#92400e"><strong>Threat Window:</strong> {window}</div>' if window else ''}
    {f'<div style="margin-top:8px;padding:10px 14px;background:#fce7f3;border-left:3px solid #ec4899;border-radius:4px;font-size:13px;color:#831843"><strong>Cross-School Alert:</strong> {cross_school}</div>' if cross_school else ''}
  </div>

  <!-- 3-Model Consensus -->
  <div style="padding:24px 32px;border-bottom:1px solid #e5e7eb;background:#f9fafb">
    <div style="font-size:11px;font-weight:600;letter-spacing:1px;color:#9ca3af;text-transform:uppercase;margin-bottom:12px">3-MODEL AI CONSENSUS</div>
    <div style="display:flex;gap:12px">
      <div style="flex:1;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:12px;text-align:center">
        <div style="font-size:10px;color:#6b7280;font-weight:600">CLAUDE</div>
        <div style="font-size:22px;font-weight:800;color:{color}">{claude_level}/5</div>
      </div>
      <div style="flex:1;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:12px;text-align:center">
        <div style="font-size:10px;color:#6b7280;font-weight:600">GEMINI</div>
        <div style="font-size:22px;font-weight:800;color:{color}">{gemini_level}/5</div>
      </div>
      <div style="flex:1;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:12px;text-align:center">
        <div style="font-size:10px;color:#6b7280;font-weight:600">BAYESIAN</div>
        <div style="font-size:22px;font-weight:800;color:{color}">{f"{bayes_pct}%" if bayes_pct else "—"}</div>
      </div>
      <div style="flex:1;background:{'#dcfce7' if consensus else '#fef3c7'};border:1px solid {'#86efac' if consensus else '#fcd34d'};border-radius:8px;padding:12px;text-align:center">
        <div style="font-size:10px;color:#6b7280;font-weight:600">CONSENSUS</div>
        <div style="font-size:15px;font-weight:700;color:{'#15803d' if consensus else '#92400e'}">{'✓ YES' if consensus else '⚠ NO'}</div>
      </div>
    </div>
    {f'<div style="margin-top:12px"><div style="font-size:11px;color:#9ca3af;font-weight:600;margin-bottom:4px">TOP BAYESIAN DRIVERS</div><ul style="margin:0;padding-left:16px">{drivers_html}</ul></div>' if bayes_drivers else ''}
  </div>

  <!-- Key Facts & Credibility -->
  <div style="padding:24px 32px;border-bottom:1px solid #e5e7eb;display:flex;gap:32px">
    <div style="flex:1">
      <div style="font-size:11px;font-weight:600;letter-spacing:1px;color:#9ca3af;text-transform:uppercase;margin-bottom:8px">KEY FACTS</div>
      <ul style="margin:0;padding-left:16px">{facts_html or '<li style="color:#9ca3af">None extracted</li>'}</ul>
    </div>
    <div style="flex:1">
      <div style="font-size:11px;font-weight:600;letter-spacing:1px;color:#9ca3af;text-transform:uppercase;margin-bottom:8px">CREDIBILITY SIGNALS</div>
      <ul style="margin:0;padding-left:16px">{cred_html or '<li style="color:#9ca3af">None detected</li>'}</ul>
    </div>
  </div>

  <!-- Caller Profile -->
  <div style="padding:24px 32px;border-bottom:1px solid #e5e7eb;background:#f9fafb">
    <div style="font-size:11px;font-weight:600;letter-spacing:1px;color:#9ca3af;text-transform:uppercase;margin-bottom:8px">CALLER PROFILE</div>
    <div style="display:flex;gap:24px;flex-wrap:wrap">
      {f'<div><span style="font-size:11px;color:#9ca3af">EMOTION</span><div style="font-weight:600;color:#111827;margin-top:2px">{emotion.title()}</div></div>' if emotion else ''}
      {f'<div><span style="font-size:11px;color:#9ca3af">ESCALATION</span><div style="font-weight:600;color:#111827;margin-top:2px">{escalation.title()}</div></div>' if escalation else ''}
      <div><span style="font-size:11px;color:#9ca3af">ANONYMOUS</span><div style="font-weight:600;color:#111827;margin-top:2px">Yes</div></div>
      <div><span style="font-size:11px;color:#9ca3af">CALL ID</span><div style="font-family:monospace;font-size:12px;color:#374151;margin-top:2px">{call_id[:12]}</div></div>
      <div><span style="font-size:11px;color:#9ca3af">TIMESTAMP</span><div style="font-size:12px;color:#374151;margin-top:2px">{timestamp}</div></div>
    </div>
  </div>

  {f'''<!-- 911 Dispatch Brief -->
  <div style="padding:24px 32px;border-bottom:1px solid #e5e7eb;background:#fff7ed">
    <div style="font-size:11px;font-weight:600;letter-spacing:1px;color:#9ca3af;text-transform:uppercase;margin-bottom:8px">911 DISPATCH BRIEF</div>
    <div style="font-size:14px;color:#111827;line-height:1.7;padding:16px;background:#fff;border-radius:8px;border:1px solid #fed7aa">{brief}</div>
  </div>''' if brief else ''}

  {f'''<!-- Supermemory Context -->
  <div style="padding:24px 32px;border-bottom:1px solid #e5e7eb">
    <div style="font-size:11px;font-weight:600;letter-spacing:1px;color:#9ca3af;text-transform:uppercase;margin-bottom:8px">HISTORICAL PATTERN CONTEXT</div>
    <div style="font-size:13px;color:#374151;background:#f3f4f6;padding:12px;border-radius:6px;line-height:1.6">{prior_context[:400]}</div>
  </div>''' if prior_context else ''}

  {f'''<!-- OSINT -->
  <div style="padding:24px 32px;border-bottom:1px solid #e5e7eb">
    <div style="font-size:11px;font-weight:600;letter-spacing:1px;color:#9ca3af;text-transform:uppercase;margin-bottom:8px">OSINT FINDINGS</div>
    <div style="font-size:13px;color:#374151;background:#f3f4f6;padding:12px;border-radius:6px;line-height:1.6">{osint[:300]}</div>
  </div>''' if osint and "unavailable" not in osint.lower() else ''}

  <!-- Footer -->
  <div style="padding:20px 32px;background:#f9fafb;text-align:center">
    <div style="font-size:11px;color:#9ca3af">Generated by <strong>Threat Vector AI</strong> · Powered by Claude, Gemini, Supermemory, AgentMail · {timestamp}</div>
    <div style="font-size:10px;color:#d1d5db;margin-top:4px">This report was generated automatically. Always verify with law enforcement for Level 4-5 threats.</div>
  </div>

</div>
</body>
</html>"""


def send_email_brief(subject: str, body: str, call_id: str, classification: dict | None = None):
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

    # Build rich HTML if classification data available
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    if classification:
        html_body = _build_html_email(classification, call_id, ts)
    else:
        html_body = f"<pre style='font-family:monospace'>{body}</pre>"

    payload = {
        "to": recipient,
        "subject": subject or f"[Threat Vector] Threat Report — {ts}",
        "text": body,  # plain text fallback
        "html": html_body,
    }
    if from_addr and from_addr not in ("FILL_IN", "threats@your-inbox.agentmail.to"):
        payload["reply_to"] = from_addr

    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=12,
        )
        if r.status_code in (200, 201):
            print(f"[{call_id}] AgentMail: HTML email sent to {recipient}")
            return True
        print(f"[{call_id}] WARNING: AgentMail returned {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"[{call_id}] WARNING: AgentMail send failed: {e}")
        return False
