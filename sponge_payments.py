"""
Sponge integration — financial infrastructure for the agent economy.
Sponge handles agent-to-agent micropayments and autonomous fund disbursement.
Used here to: (1) pay the OSINT agent for each search, (2) track spend per district.
"""
import os
import requests

SPONGE_BASE = os.getenv("SPONGE_BASE", "https://api.wallet.paysponge.com/mcp")

def disburse_agent_payment(service: str, amount_cents: int, call_id: str, metadata: dict = {}) -> dict | None:
    """
    Pay an agent service (e.g., OSINT lookup, SMS dispatch) from the district's Sponge wallet.
    Demonstrates autonomous agent-to-agent financial transactions.
    """
    key = os.getenv("SPONGE_API_KEY")
    wallet_id = os.getenv("SPONGE_WALLET_ID")

    if not key or key == "FILL_IN":
        print(f"[{call_id}] WARNING: Sponge API key not set — skipping agent payment")
        return None

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
        print(f"[{call_id}] WARNING: Sponge returned {response.status_code}: {response.text[:100]}")
    except Exception as e:
        print(f"[{call_id}] WARNING: Sponge payment failed: {e}")
    return None


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
