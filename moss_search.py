"""
Moss integration — real-time semantic search during the voice call.

Moss no longer uses the guessed https://api.moss.ai/v1/search endpoint.
The current SDK authenticates with MOSS_PROJECT_ID + MOSS_PROJECT_KEY and
queries/indexes named indexes through MossClient. See:
https://docs.moss.dev/docs/reference/python/classes/MossClient
"""
import os

DEFAULT_INDEX = "threat-vector-tips"

_client = None

def _get_client(call_id: str):
    global _client
    project_id = os.getenv("MOSS_PROJECT_ID", "")
    project_key = os.getenv("MOSS_PROJECT_KEY") or os.getenv("MOSS_API_KEY", "")
    if not project_id or project_id == "FILL_IN" or not project_key or project_key == "FILL_IN":
        print(f"[{call_id}] WARNING: Moss project credentials not set — skipping semantic search")
        return None

    if _client is None:
        try:
            from moss import MossClient
            _client = MossClient(project_id, project_key)
        except ImportError:
            print(f"[{call_id}] WARNING: moss SDK not installed — skipping semantic search")
            return None
        except Exception as e:
            print(f"[{call_id}] WARNING: Moss client init failed: {e}")
            return None
    return _client

def _doc_get(doc, key: str, default=None):
    if isinstance(doc, dict):
        return doc.get(key, default)
    return getattr(doc, key, default)

def semantic_search_tips(query: str, call_id: str) -> str:
    """
    Run semantic search against indexed tip history.
    Returns a short context string for Claude.
    """
    client = _get_client(call_id)
    if client is None:
        return ""

    index_name = os.getenv("MOSS_INDEX_ID") or DEFAULT_INDEX
    top_k = int(os.getenv("MOSS_TOP_K", "3"))

    try:
        result = client.query(index_name, query, {"top_k": top_k, "alpha": 0.8})
        docs = _doc_get(result, "docs", []) or _doc_get(result, "documents", []) or []
        if not docs:
            return ""

        snippets = []
        for doc in docs[:top_k]:
            text = _doc_get(doc, "text", "") or _doc_get(doc, "content", "")
            score = _doc_get(doc, "score", None)
            prefix = f"{score:.2f}: " if isinstance(score, (int, float)) else ""
            if text:
                snippets.append(f"{prefix}{text[:120]}")

        if not snippets:
            return ""

        print(f"[{call_id}] Moss: {len(docs)} semantic matches found")
        return "Semantic matches from prior tips: " + " | ".join(snippets)
    except Exception as e:
        print(f"[{call_id}] WARNING: Moss semantic search failed: {e}")
        return ""

def index_tip(tip_text: str, metadata: dict, call_id: str):
    """Index a processed tip into Moss so future calls can find it semantically."""
    client = _get_client(call_id)
    if client is None:
        return

    index_name = os.getenv("MOSS_INDEX_ID") or DEFAULT_INDEX
    doc = {
        "id": call_id,
        "text": tip_text,
        "metadata": metadata,
    }

    try:
        client.add_docs(index_name, [doc], {"upsert": True})
        print(f"[{call_id}] Moss: tip indexed for future semantic search")
    except Exception as e:
        print(f"[{call_id}] WARNING: Moss index failed: {e}")
