"""
Moss integration — real-time semantic search during the voice call.
Moss is used to query prior tips semantically as the caller speaks,
giving the agent live context before classification even runs.
"""
import os
import requests

MOSS_BASE = "https://api.moss.ai/v1"  # Update if Moss provides a different endpoint at hackathon

def semantic_search_tips(query: str, call_id: str) -> str:
    """
    Run a real-time semantic search against indexed tip history.
    Called by the agent before classification to give Claude richer context.
    """
    key = os.getenv("MOSS_API_KEY")
    if not key or key == "FILL_IN":
        print(f"[{call_id}] WARNING: Moss API key not set — skipping semantic search")
        return ""

    try:
        response = requests.post(
            f"{MOSS_BASE}/search",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "query": query,
                "top_k": 3,
                "index": os.getenv("MOSS_INDEX_ID", "threat-vector-tips"),
            },
            timeout=8,
        )
        if response.status_code != 200:
            print(f"[{call_id}] WARNING: Moss returned {response.status_code}: {response.text[:100]}")
            return ""

        results = response.json().get("results", [])
        if not results:
            return ""

        snippets = [r.get("text", "")[:120] for r in results[:3]]
        context = f"Semantic matches from prior tips: " + " | ".join(snippets)
        print(f"[{call_id}] Moss: {len(results)} semantic matches found")
        return context

    except Exception as e:
        print(f"[{call_id}] WARNING: Moss semantic search failed: {e}")
        return ""


def index_tip(tip_text: str, metadata: dict, call_id: str):
    """Index a processed tip into Moss so future calls can find it semantically."""
    key = os.getenv("MOSS_API_KEY")
    if not key or key == "FILL_IN":
        return

    try:
        requests.post(
            f"{MOSS_BASE}/index",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "text": tip_text,
                "metadata": metadata,
                "index": os.getenv("MOSS_INDEX_ID", "threat-vector-tips"),
            },
            timeout=8,
        )
        print(f"[{call_id}] Moss: tip indexed for future semantic search")
    except Exception as e:
        print(f"[{call_id}] WARNING: Moss index failed: {e}")
