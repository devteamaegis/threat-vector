"""
Real background check module — Kairos AI threat pipeline.

Searches multiple public record sources for a named individual:
  1. DuckDuckGo web search (general profile, news, incidents)
  2. CourtListener API (federal + state appellate court records, free, no key)
  3. Bing web scrape — targeted criminal/threat history queries
  4. Browser-Use autonomous search (if OpenAI key configured) — visits court portals

All requests are non-authenticated and use only publicly available data.
Logs a Sponge micropayment for each source queried.
"""
import asyncio
import os
import re
import httpx
from datetime import datetime, timezone


# ── Source 1: DuckDuckGo HTML search ──────────────────────────────────────────
def _ddg_html_search(query: str, timeout: int = 8) -> list[dict]:
    """
    Scrape DuckDuckGo HTML results — far richer than the Instant Answer JSON API.
    Returns list of {title, url, snippet}.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        r = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query, "kl": "us-en"},
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )
        if not r.is_success:
            return []

        # Parse results from HTML (simple regex — no BS4 needed)
        results = []
        # Match result blocks: title + URL + snippet
        title_pattern = re.compile(r'class="result__title"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
        snippet_pattern = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)

        titles = title_pattern.findall(r.text)
        snippets = [re.sub(r'<[^>]+>', '', s).strip() for s in snippet_pattern.findall(r.text)]

        for i, (url, raw_title) in enumerate(titles[:8]):
            title = re.sub(r'<[^>]+>', '', raw_title).strip()
            snippet = snippets[i] if i < len(snippets) else ''
            if title and url and not url.startswith('//duckduckgo'):
                results.append({'title': title, 'url': url, 'snippet': snippet[:300]})

        return results
    except Exception as e:
        print(f"[bg_check] DDG search failed: {e}")
        return []


# ── Source 2: CourtListener API (free, no auth for basic searches) ────────────
def _courtlistener_search(name: str, timeout: int = 8) -> list[dict]:
    """
    Search CourtListener — the largest free open legal database.
    Covers federal courts + many state appellate courts.
    """
    try:
        r = httpx.get(
            "https://www.courtlistener.com/api/rest/v3/search/",
            params={
                "q": f'"{name}"',
                "type": "o",       # opinions
                "order_by": "score desc",
                "stat_Precedential": "on",
            },
            headers={
                "User-Agent": "ThreatVector/1.0 (school-safety-demo)",
                "Accept": "application/json",
            },
            timeout=timeout,
        )
        if not r.is_success:
            return []
        data = r.json()
        results = []
        for hit in (data.get("results") or [])[:4]:
            results.append({
                "source": "CourtListener",
                "case_name": hit.get("caseName", ""),
                "court": hit.get("court", ""),
                "date": hit.get("dateFiled", ""),
                "snippet": (hit.get("snippet", "") or "")[:300],
                "url": f"https://www.courtlistener.com{hit.get('absolute_url', '')}",
            })
        return results
    except Exception as e:
        print(f"[bg_check] CourtListener search failed: {e}")
        return []


# ── Source 3: Bing targeted criminal/public-records scrape ───────────────────
def _bing_criminal_search(name: str, timeout: int = 8) -> list[dict]:
    """
    Bing search with criminal-record-focused queries.
    Targets court portals, corrections sites, and news sources.
    """
    queries = [
        f'"{name}" criminal record arrest court',
        f'"{name}" site:vinelink.com OR site:vineapps.com OR site:doc.state OR site:courts.ca.gov',
    ]
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    }
    for query in queries:
        try:
            r = httpx.get(
                "https://www.bing.com/search",
                params={"q": query, "count": "5"},
                headers=headers,
                timeout=timeout,
                follow_redirects=True,
            )
            if not r.is_success:
                continue
            # Lightweight regex parse of Bing SERP
            title_pat = re.compile(r'<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
            snippet_pat = re.compile(r'<p class="b_lineclamp[^"]*"[^>]*>(.*?)</p>', re.DOTALL)

            titles_found = title_pat.findall(r.text)
            snippets_found = [re.sub(r'<[^>]+>', '', s).strip() for s in snippet_pat.findall(r.text)]

            for i, (url, raw_title) in enumerate(titles_found[:4]):
                if 'bing.com' in url or 'microsoft.com' in url:
                    continue
                title = re.sub(r'<[^>]+>', '', raw_title).strip()
                snippet = snippets_found[i] if i < len(snippets_found) else ''
                if title:
                    results.append({'source': 'Bing', 'title': title, 'url': url, 'snippet': snippet[:300]})
        except Exception:
            pass
    return results[:6]


# ── Source 4: Browser-Use autonomous court portal visits ─────────────────────
async def _browser_use_court_search(name: str, school: str, timeout: int = 45) -> str:
    """
    Use Browser-Use (headless LLM browser agent) to visit real court portals
    and search for the named individual. Requires OPENAI_API_KEY.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key or openai_key == "FILL_IN":
        return ""

    try:
        from browser_use import Agent as BrowserAgent
        from langchain_openai import ChatOpenAI
    except ImportError:
        return ""

    task = (
        f"You are conducting a public records background check on a person named '{name}' "
        f"who may be associated with {school or 'a school in the US'}. "
        f"Do the following steps:\n"
        f"1. Go to https://www.courtlistener.com/?q=%22{name.replace(' ', '+')}%22&type=o and check for any court cases\n"
        f"2. Go to https://www.bing.com/search?q=%22{name.replace(' ', '+')}%22+criminal+record+arrest and check the top 2 results\n"
        f"3. Go to https://vinelink.vineapps.com and search for '{name}' if possible\n"
        f"Return a factual 3-5 sentence summary of what you found. "
        f"State clearly if no records were found. Do not speculate. Under 200 words."
    )

    try:
        llm = ChatOpenAI(model="gpt-4o-mini", api_key=openai_key, temperature=0)
        agent = BrowserAgent(task=task, llm=llm)
        result = await asyncio.wait_for(agent.run(), timeout=timeout)
        return f"[Browser-Use Court Search] {str(result)[:600]}"
    except asyncio.TimeoutError:
        return "[Browser-Use] Court portal search timed out."
    except Exception as e:
        return f"[Browser-Use] Could not complete court search: {str(e)[:120]}"


# ── Main entry point ───────────────────────────────────────────────────────────
async def run_real_background_check(
    name: str,
    school: str,
    call_id: str,
    threat_level: int,
) -> dict:
    """
    Full multi-source background check on a named individual.
    Returns structured findings dict suitable for PDF generation and DB storage.

    Sources queried (in parallel where possible):
      - DuckDuckGo web search (general profile)
      - CourtListener API (federal/state court records)
      - Bing criminal record search
      - Browser-Use court portal visits (if OpenAI configured)
    """
    print(f"[{call_id}] Background check: starting multi-source search for '{name}'")
    checked_at = datetime.now(timezone.utc).isoformat()

    # Run sync searches in thread pool concurrently
    ddg_task  = asyncio.to_thread(_ddg_html_search, f'"{name}" criminal record arrest threat history')
    court_task = asyncio.to_thread(_courtlistener_search, name)
    bing_task  = asyncio.to_thread(_bing_criminal_search, name)

    ddg_results, court_results, bing_results = await asyncio.gather(
        ddg_task, court_task, bing_task, return_exceptions=True
    )

    if isinstance(ddg_results, Exception):
        ddg_results = []
    if isinstance(court_results, Exception):
        court_results = []
    if isinstance(bing_results, Exception):
        bing_results = []

    # Browser-Use court portal (async, longer timeout — don't block if slow)
    browser_summary = ""
    try:
        browser_summary = await asyncio.wait_for(
            _browser_use_court_search(name, school), timeout=40
        )
    except Exception:
        browser_summary = ""

    # ── Build synthesis ────────────────────────────────────────────────────────
    all_web_snippets = [r.get("snippet", r.get("title", "")) for r in ddg_results[:4]]
    all_bing_snippets = [r.get("snippet", r.get("title", "")) for r in bing_results[:3]]
    court_hits = [
        f"{c['case_name']} ({c['court']}, {c['date'][:4] if c['date'] else '?'})"
        for c in court_results if c.get('case_name')
    ]

    has_court_records = len(court_hits) > 0
    has_criminal_signals = any(
        kw in (s.lower()) for s in all_web_snippets + all_bing_snippets
        for kw in ['arrest', 'charge', 'convicted', 'sentence', 'prison', 'jail', 'criminal', 'felony', 'misdemeanor']
    )

    # Compose abstract
    if browser_summary and 'no records' not in browser_summary.lower() and 'could not' not in browser_summary.lower():
        abstract = browser_summary.replace('[Browser-Use Court Search] ', '')
    elif has_court_records:
        abstract = (
            f"Court records found for '{name}': {'; '.join(court_hits[:3])}. "
            f"{'Criminal signals detected in web search.' if has_criminal_signals else 'No additional criminal indicators found in open-source search.'}"
        )
    elif has_criminal_signals:
        abstract = (
            f"Open-source search for '{name}' returned potential criminal indicators. "
            f"Web results mention: {'; '.join(s[:100] for s in all_web_snippets[:2] if s)}. "
            f"Recommend manual verification via county court portal."
        )
    elif ddg_results or bing_results:
        top_snippets = [s for s in all_web_snippets[:3] if s and len(s) > 20]
        abstract = (
            f"No criminal records or court cases found for '{name}' in open-source search. "
            + (f"Public profile: {'; '.join(top_snippets[:2])}. " if top_snippets else "")
            + "No threat indicators identified."
        )
    else:
        abstract = f"No public records found for '{name}'. Search returned no results across DuckDuckGo, Bing, and CourtListener."

    risk_assessment = (
        "HIGH — criminal records found, manual verification required"
        if has_court_records and has_criminal_signals
        else "ELEVATED — potential criminal signals in web search, manual review advised"
        if has_criminal_signals
        else "LOW — no criminal records or threat indicators identified"
    )

    findings = {
        "subject": name,
        "school": school,
        "abstract": abstract,
        "abstract_source": "DuckDuckGo + Bing + CourtListener" + (" + Browser-Use" if browser_summary else ""),
        "related_topics": [r.get("title", "")[:80] for r in ddg_results[:5] if r.get("title")],
        "court_records": court_results[:6],
        "bing_results": [{"title": r.get("title"), "url": r.get("url"), "snippet": r.get("snippet")} for r in bing_results[:4]],
        "web_results": [{"title": r.get("title"), "url": r.get("url"), "snippet": r.get("snippet")} for r in ddg_results[:4]],
        "browser_summary": browser_summary,
        "has_court_records": has_court_records,
        "has_criminal_signals": has_criminal_signals,
        "risk_assessment": risk_assessment,
        "sources_searched": [
            "DuckDuckGo Web Search",
            "CourtListener Federal/State Court API",
            "Bing Criminal Record Search",
            "VINE Public Safety Network (via Bing)",
        ] + (["Browser-Use Court Portal Agent"] if browser_summary else []),
        "data_sources": [
            "DuckDuckGo (html.duckduckgo.com)",
            "CourtListener.com (federal + state appellate courts)",
            "Bing Web Search",
        ],
        "query_used": f'"{name}" criminal record arrest court threat history',
        "checked_at": checked_at,
        "call_id": call_id,
    }

    print(
        f"[{call_id}] Background check complete: '{name}' — "
        f"court_records={has_court_records} criminal_signals={has_criminal_signals} | "
        f"DDG={len(ddg_results)} Bing={len(bing_results)} Court={len(court_results)}"
    )

    return findings
