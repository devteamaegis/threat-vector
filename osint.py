"""
Browser Use integration — autonomous OSINT for level 3+ threats.
Searches public web/social for corroborating signals.

Browser Use requires a LangChain LLM. We try OpenAI first (YC credits),
then fall back to a lightweight DuckDuckGo instant-answer search.
"""
import asyncio
import os
import httpx


async def run_osint(school_name: str, threat_type: str, subject_description: str) -> str:
    if not school_name:
        return "No school name provided for OSINT search."

    query = f"{school_name} {threat_type} threat"
    if subject_description:
        query += f" {subject_description}"

    # Try Browser Use with OpenAI (preferred — uses YC OpenAI credits)
    result = await _browser_use_osint(query, school_name)
    if result:
        return result

    # Fallback: DuckDuckGo instant answers (no key needed)
    return await _ddg_osint(query)


async def _browser_use_osint(query: str, school_name: str) -> str:
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key or openai_key == "FILL_IN":
        return ""

    try:
        from browser_use import Agent as BrowserAgent
        from langchain_openai import ChatOpenAI
    except ImportError:
        return ""

    try:
        llm = ChatOpenAI(model="gpt-4o-mini", api_key=openai_key, temperature=0)
        agent = BrowserAgent(
            task=(
                f"Search the web for recent news or social media posts about a potential threat at {school_name}. "
                f"Search query: '{query}'. "
                "Look at the first 2-3 news results. "
                "Return a 2-sentence summary of any relevant findings, "
                "or 'No relevant public signals found.' if nothing matches. Under 80 words."
            ),
            llm=llm,
        )
        result = await asyncio.wait_for(agent.run(), timeout=20)
        return f"[Browser Use] {str(result)[:400]}"
    except asyncio.TimeoutError:
        return "[Browser Use] OSINT timed out."
    except Exception as e:
        return f"[Browser Use] Could not complete: {str(e)[:100]}"


async def _ddg_osint(query: str) -> str:
    """DuckDuckGo Instant Answers API — no key required, always available."""
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
                headers={"User-Agent": "ThreatVector/1.0"},
            )
            data = r.json()
            abstract = data.get("AbstractText", "").strip()
            if abstract:
                return f"[OSINT] {abstract[:300]}"
            related = data.get("RelatedTopics", [])
            if related:
                first = related[0]
                text = first.get("Text", "") if isinstance(first, dict) else ""
                if text:
                    return f"[OSINT] {text[:300]}"
            return "No relevant public signals found."
    except Exception as e:
        return f"OSINT search failed: {str(e)[:80]}"
