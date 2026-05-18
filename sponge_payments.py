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
    wallet_id = os.getenv("SPONGE_WALLET_ID")

    if not key or key == "FILL_IN" or not wallet_id or wallet_id == "FILL_IN":
        return None  # Sponge not configured — skip silently

    try:
        response = requests.post(
            f"{SPONGE_BASE}/payments",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "wallet_id": wallet_id,
                "amount": amount_cents,
                "currency": "usd",
                "service": service,
                "reference": call_id,
                "metadata": {**metadata, "call_id": call_id},
            },
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


def get_recent_transactions(limit: int = 10) -> list:
    """Fetch recent agent payment transactions for the dashboard ticker."""
    key = os.getenv("SPONGE_API_KEY")
    wallet_id = os.getenv("SPONGE_WALLET_ID")
    if not key or key == "FILL_IN" or not wallet_id or wallet_id == "FILL_IN":
        # Return demo transactions for display when wallet not configured
        return [
            {"service": "browser-use-osint", "amount": 0.02, "label": "OSINT Search", "icon": "🔍"},
            {"service": "twilio-sms", "amount": 0.01, "label": "SMS Alert", "icon": "📱"},
            {"service": "agentmail-brief", "amount": 0.01, "label": "Email Brief", "icon": "✉️"},
            {"service": "gemini-verify", "amount": 0.03, "label": "Gemini Verify", "icon": "✦"},
            {"service": "supermemory-store", "amount": 0.005, "label": "Memory Store", "icon": "🧬"},
        ]
    try:
        r = requests.get(
            f"{SPONGE_BASE}/wallets/{wallet_id}/transactions?limit={limit}",
            headers={"Authorization": f"Bearer {key}"},
            timeout=5,
        )
        if r.ok:
            return r.json().get("transactions", [])
    except Exception:
        pass
    return []
