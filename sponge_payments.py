"""
Sponge integration — financial infrastructure for the agent economy.
Sponge handles agent-to-agent micropayments and autonomous fund disbursement.
Used here to: (1) pay the OSINT agent for each search, (2) track spend per district.
"""
import os
import requests

SPONGE_BASE = os.getenv("SPONGE_BASE", "https://api.wallet.paysponge.com")

def disburse_agent_payment(service: str, amount_cents: int, call_id: str, metadata: dict = {}) -> dict | None:
    """
    Pay an agent service (e.g., OSINT lookup, SMS dispatch) from the district's Sponge wallet.
    Demonstrates autonomous agent-to-agent financial transactions.
    """
    key = os.getenv("SPONGE_API_KEY")

    if not key or key == "FILL_IN":
        return None  # Sponge not configured — skip silently

    # wallet_id is optional — Sponge derives it from the API key
    wallet_id = os.getenv("SPONGE_WALLET_ID") or None

    try:
        payload: dict = {
            "amount": amount_cents,
            "currency": "usd",
            "service": service,
            "reference": call_id,
            "metadata": {**metadata, "call_id": call_id},
        }
        if wallet_id and wallet_id != "FILL_IN":
            payload["wallet_id"] = wallet_id

        response = requests.post(
            f"{SPONGE_BASE}/payments",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=8,
        )
        if response.status_code in (200, 201):
            data = response.json()
            tx_id = data.get("transaction_id", "demo")
            print(f"[{call_id}] Sponge: paid {service} ${amount_cents/100:.2f} (tx: {tx_id})")
            return data
        print(f"[{call_id}] Sponge: {response.status_code} ({service})")
    except Exception as e:
        print(f"[{call_id}] WARNING: Sponge payment failed: {e}")
    return None


def authorize_background_check(subject: str, school: str, call_id: str, threat_level: int) -> dict:
    """
    Authorize a micro-payment for a background check via Sponge before each OSINT lookup.
    Creates an auditable transaction receipt demonstrating autonomous AI purchasing.
    Returns a result dict regardless of whether Sponge is configured.
    """
    amount_cents = threat_level * 1  # level 3 = 3¢, level 4 = 4¢, level 5 = 5¢
    result = disburse_agent_payment(
        service="background-check-agent",
        amount_cents=amount_cents,
        call_id=call_id,
        metadata={
            "subject": subject,
            "school": school,
            "threat_level": threat_level,
            "type": "background_check",
        },
    )
    if result is None:
        # Sponge not configured — return a demo receipt so the demo always shows something
        return {
            "authorized": True,
            "amount_cents": 0,
            "tx_id": "demo-receipt",
            "subject": subject,
        }
    tx_id = result.get("transaction_id") or result.get("tx_id") or result.get("id") or "demo"
    return {
        "authorized": True,
        "amount_cents": amount_cents,
        "tx_id": tx_id,
        "subject": subject,
    }


def run_paid_background_check(subject_name: str, school: str, call_id: str, threat_level: int, known_facts: list | None = None) -> dict:
    """
    Full paid background check:
    1. Authorize micropayment via Sponge
    2. Run multi-source web background check (DuckDuckGo + CourtListener + Bing)
    3. Log transaction to Supabase
    4. Return structured result with payment receipt + findings
    """
    import asyncio

    receipt = authorize_background_check(subject_name, school, call_id, threat_level)

    # Run the async multi-source background check in a new event loop
    # (this function is called from asyncio.to_thread so we can't await directly)
    try:
        from background_check import run_real_background_check
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an event loop (e.g. called from asyncio.to_thread)
                # Use a fresh loop in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        lambda: asyncio.run(
                            run_real_background_check(subject_name, school, call_id, threat_level)
                        )
                    )
                    findings = future.result(timeout=55)
            else:
                findings = loop.run_until_complete(
                    run_real_background_check(subject_name, school, call_id, threat_level)
                )
        except Exception as e:
            print(f"[{call_id}] WARNING: Real background check failed: {e}")
            findings = _ddg_fallback(subject_name, school, call_id)
    except ImportError:
        findings = _ddg_fallback(subject_name, school, call_id)

    log_transaction_to_supabase({
        **receipt,
        "findings_summary": f"Subject: {subject_name}. {findings.get('abstract', '')[:400]}",
    }, call_id)

    return {**receipt, "findings": findings, "check_complete": True}


def _ddg_fallback(subject_name: str, school: str, call_id: str) -> dict:
    """Simple DuckDuckGo fallback if the real background check fails."""
    import httpx
    from datetime import datetime, timezone
    try:
        r = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": f'"{subject_name}" {school}', "format": "json", "no_html": 1},
            timeout=8,
        )
        data = r.json()
        abstract = data.get("AbstractText", data.get("Abstract", ""))
    except Exception:
        abstract = ""
    return {
        "subject": subject_name,
        "school": school,
        "abstract": abstract or f"No public records found for '{subject_name}'.",
        "abstract_source": "DuckDuckGo (fallback)",
        "related_topics": [],
        "court_records": [],
        "risk_assessment": "LOW — no records found",
        "data_sources": ["DuckDuckGo"],
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def log_transaction_to_supabase(tx_data: dict, call_id: str) -> None:
    """
    Log a Sponge transaction to the sponge_transactions Supabase table for audit trails.
    Never raises — failures are swallowed and printed as warnings.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        return
    try:
        from datetime import datetime, timezone
        payload = {
            "call_id": call_id,
            "service": "background-check-agent",
            "amount_cents": tx_data.get("amount_cents", 0),
            "subject": tx_data.get("subject", ""),
            "school": tx_data.get("school", ""),
            "tx_id": tx_data.get("tx_id"),
            "threat_level": tx_data.get("threat_level"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        requests.post(
            f"{supabase_url}/rest/v1/sponge_transactions",
            headers={
                "apikey": service_role_key,
                "Authorization": f"Bearer {service_role_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=payload,
            timeout=6,
        )
    except Exception as e:
        print(f"[{call_id}] WARNING: Failed to log Sponge transaction to Supabase: {e}")


def get_wallet_balance(call_id: str = "system") -> float | None:
    """Fetch district wallet balance — shown on dashboard as agent spend tracker."""
    key = os.getenv("SPONGE_API_KEY")
    wallet_id = os.getenv("SPONGE_WALLET_ID")
    if not key or key == "FILL_IN":
        return None
    try:
        r = requests.get(
            f"{SPONGE_BASE}/wallets/{wallet_id}",
            headers={"Authorization": f"Bearer {key}"},
            timeout=5,
        )
        return r.json().get("balance_cents", 0) / 100 if r.ok else None
    except Exception:
        return None


def get_recent_transactions(limit: int = 20) -> list:
    """
    Fetch recent agent payment transactions for the dashboard.
    Priority order:
      1. Sponge API (if wallet_id configured)
      2. Supabase sponge_transactions table (always written to on each payment)
      3. Hardcoded demo data (last resort when nothing is configured)
    """
    key = os.getenv("SPONGE_API_KEY")
    wallet_id = os.getenv("SPONGE_WALLET_ID")

    # 1. Try Sponge API (requires both key + wallet_id)
    if key and key != "FILL_IN" and wallet_id and wallet_id != "FILL_IN":
        try:
            r = requests.get(
                f"{SPONGE_BASE}/wallets/{wallet_id}/transactions?limit={limit}",
                headers={"Authorization": f"Bearer {key}"},
                timeout=5,
            )
            if r.ok:
                raw = r.json().get("transactions", [])
                if raw:
                    return raw
        except Exception:
            pass

    # 2. Read from Supabase sponge_transactions (written by log_transaction_to_supabase)
    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if supabase_url and service_role_key:
        try:
            r = requests.get(
                f"{supabase_url}/rest/v1/sponge_transactions"
                f"?order=created_at.desc&limit={limit}",
                headers={
                    "apikey": service_role_key,
                    "Authorization": f"Bearer {service_role_key}",
                },
                timeout=5,
            )
            if r.ok:
                rows = r.json()
                if rows:
                    # Normalise column names to what the frontend expects
                    return [
                        {
                            "service":    row.get("service", "unknown"),
                            "amount":     (row.get("amount_cents") or 0) / 100,
                            "label":      _service_label(row.get("service", "")),
                            "icon":       _service_icon(row.get("service", "")),
                            "call_id":    row.get("call_id"),
                            "subject":    row.get("subject"),
                            "tx_id":      row.get("tx_id"),
                            "created_at": row.get("created_at"),
                        }
                        for row in rows
                    ]
        except Exception:
            pass

    # 3. Demo fallback
    return [
        {"service": "browser-use-osint", "amount": 0.02, "label": "OSINT Search",    "icon": "🔍"},
        {"service": "twilio-sms",         "amount": 0.01, "label": "SMS Alert",       "icon": "📱"},
        {"service": "agentmail-brief",    "amount": 0.01, "label": "Email Brief",     "icon": "✉️"},
        {"service": "gemini-verify",      "amount": 0.03, "label": "Gemini Verify",   "icon": "✦"},
        {"service": "supermemory-store",  "amount": 0.005,"label": "Memory Store",    "icon": "🧬"},
    ]


_SERVICE_LABELS = {
    "background-check-agent": "Background Check",
    "browser-use-osint":      "OSINT Search",
    "twilio-sms":             "SMS Alert",
    "agentmail-brief":        "Email Brief",
    "gemini-verify":          "Gemini Verify",
    "supermemory-store":      "Memory Store",
}
_SERVICE_ICONS = {
    "background-check-agent": "🕵️",
    "browser-use-osint":      "🔍",
    "twilio-sms":             "📱",
    "agentmail-brief":        "✉️",
    "gemini-verify":          "✦",
    "supermemory-store":      "🧬",
}

def _service_label(svc: str) -> str:
    return _SERVICE_LABELS.get(svc, svc)

def _service_icon(svc: str) -> str:
    return _SERVICE_ICONS.get(svc, "💰")
