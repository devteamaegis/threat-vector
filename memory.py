import os
from datetime import datetime
from supermemory import Supermemory

CONTAINER_TAG = "threat-vector-tips"


def _client() -> Supermemory | None:
    key = os.getenv("SUPERMEMORY_API_KEY", "")
    if not key or key == "FILL_IN":
        return None
    return Supermemory(api_key=key)


def store_tip_memory(classification: dict, call_id: str):
    client = _client()
    if not client:
        print(f"[{call_id}] WARNING: SUPERMEMORY_API_KEY not set — skipping memory store")
        return

    school = classification.get("school_name") or "unknown school"
    threat_type = classification.get("threat_type", "unknown")
    level = classification.get("threat_level", 0)
    facts = "; ".join(classification.get("key_facts") or [])
    summary = classification.get("summary", "")

    content = (
        f"Threat report at {school}. "
        f"Type: {threat_type}. Level: {level}/5. "
        f"Timeline: {classification.get('timeline', 'unknown')}. "
        f"Escalation risk: {classification.get('escalation_risk', 'unknown')}. "
        f"Recommended action: {classification.get('recommended_action', 'unknown')}. "
        f"Key facts: {facts}. "
        f"Summary: {summary} "
        f"Call ID: {call_id}. Timestamp: {datetime.utcnow().isoformat()}"
    )

    try:
        client.add(
            content=content,
            container_tag=CONTAINER_TAG,
            custom_id=call_id,
            metadata={
                "school": school,
                "call_id": call_id,
                "level": str(level),
                "threat_type": threat_type,
            },
        )
        print(f"[{call_id}] Supermemory: stored tip for {school}")
    except Exception as e:
        print(f"[{call_id}] WARNING: Supermemory store failed: {e}")


def search_prior_tips(school_name: str) -> str:
    client = _client()
    if not client or not school_name:
        return ""

    try:
        resp = client.search.execute(
            q=f"threat report {school_name}",
            container_tag=CONTAINER_TAG,
            limit=3,
            rerank=True,
        )
        results = getattr(resp, "results", None) or []
        if not results:
            return ""
        summaries = []
        for r in results:
            chunk = getattr(r, "content", None) or getattr(r, "text", "") or ""
            summaries.append(str(chunk)[:120])
        return f"Prior tips for {school_name}: " + " | ".join(summaries)
    except Exception as e:
        print(f"WARNING: Supermemory search failed: {e}")
        return ""
