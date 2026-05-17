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
    credibility = "; ".join(classification.get("credibility_signals") or [])
    window = classification.get("threat_window", "")
    consensus = classification.get("three_model_consensus", False)

    # Rich content — more signals = better cross-school semantic recall
    content = (
        f"Threat report at {school}. "
        f"Type: {threat_type}. Level: {level}/5. "
        f"Timeline: {classification.get('timeline', 'unknown')}. "
        f"Threat window: {window}. "
        f"Escalation risk: {classification.get('escalation_risk', 'unknown')}. "
        f"Caller emotion: {classification.get('caller_emotion', 'unknown')}. "
        f"Recommended action: {classification.get('recommended_action', 'unknown')}. "
        f"Credibility signals: {credibility}. "
        f"3-model consensus: {'yes' if consensus else 'no'}. "
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
                "escalation_risk": classification.get("escalation_risk", "unknown"),
                "historical": "false",
            },
        )
        print(f"[{call_id}] Supermemory: stored tip for {school} (level {level})")
    except Exception as e:
        print(f"[{call_id}] WARNING: Supermemory store failed: {e}")


def _search(client: Supermemory, query: str, limit: int = 5) -> list:
    try:
        resp = client.search.execute(
            q=query,
            container_tag=CONTAINER_TAG,
            limit=limit,
            rerank=True,
        )
        return getattr(resp, "results", None) or []
    except Exception as e:
        print(f"WARNING: Supermemory search failed for '{query[:50]}': {e}")
        return []


def search_prior_tips(school_name: str, threat_type: str = "", key_facts: list | None = None) -> str:
    """
    Multi-dimensional search across 3 axes:
    1. Same school — any prior incidents
    2. Same threat type across all schools — detect district-wide patterns
    3. Behavioral signals — cross-school matching on key facts
    Returns a combined context string injected into Claude's classification prompt.
    """
    client = _client()
    if not client:
        return ""

    segments: list[str] = []

    # Axis 1: same school prior incidents
    if school_name:
        results = _search(client, f"threat report {school_name}", limit=3)
        if results:
            snippets = [str(getattr(r, "content", "") or "")[:140] for r in results]
            segments.append(f"Prior at {school_name}: " + " | ".join(snippets))

    # Axis 2: same threat type — pattern across all schools
    if threat_type and threat_type not in ("other", "unknown", "general"):
        results = _search(client, f"{threat_type} school threat escalating", limit=5)
        if results:
            # Count credible vs total for context quality
            credible = sum(1 for r in results if "credible" in str(getattr(r, "content", "")).lower()
                           or "level: 4" in str(getattr(r, "content", "")).lower()
                           or "level: 5" in str(getattr(r, "content", "")).lower())
            snippets = [str(getattr(r, "content", "") or "")[:120] for r in results[:3]]
            segments.append(
                f"District-wide {threat_type} pattern ({credible}/{len(results)} high-severity): "
                + " | ".join(snippets)
            )

    # Axis 3: behavioral key facts — cross-school behavioral matching
    if key_facts and len(key_facts) >= 2:
        behavioral_query = " ".join(key_facts[:3])
        results = _search(client, f"{behavioral_query} school threat", limit=4)
        if results:
            snippets = [str(getattr(r, "content", "") or "")[:120] for r in results[:2]]
            segments.append(f"Behavioral pattern matches: " + " | ".join(snippets))

    if not segments:
        return ""

    combined = " || ".join(segments)
    print(f"Supermemory: {len(segments)}-axis context ({len(combined)} chars)")
    return combined[:700]


def search_historical_patterns(threat_type: str, call_id: str = "system") -> str:
    """Query only historical records for credibility baseline."""
    client = _client()
    if not client:
        return ""
    try:
        results = _search(client, f"Historical {threat_type} school threat outcome credible", limit=5)
        if not results:
            return ""
        credible = sum(1 for r in results
                       if "credible" in str(getattr(r, "content", "")).lower())
        total = len(results)
        return f"Historical: {total} similar {threat_type} threats — {credible} were credible ({int(credible/total*100)}%)."
    except Exception as e:
        print(f"[{call_id}] WARNING: Supermemory historical search failed: {e}")
        return ""
