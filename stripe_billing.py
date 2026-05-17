"""
Stripe integration — charges the district a micro-fee per processed tip.
Demonstrates agentic payments: the agent autonomously bills for each tip it handles.
"""
import os
import stripe

def charge_for_tip(classification: dict, call_id: str) -> dict | None:
    key = os.getenv("STRIPE_SECRET_KEY")
    customer_id = os.getenv("STRIPE_CUSTOMER_ID")  # district's Stripe customer

    if not key or key == "FILL_IN":
        print(f"[{call_id}] WARNING: Stripe key not set — skipping billing")
        return None

    stripe.api_key = key
    level = classification.get("threat_level", 3)
    school = classification.get("school_name", "Unknown School")
    threat_type = classification.get("threat_type", "other")

    # Tiered pricing: $0.10 base + $0.05 per threat level
    amount_cents = 10 + (level * 5)

    try:
        if customer_id and customer_id != "FILL_IN":
            # Charge existing district customer
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="usd",
                customer=customer_id,
                description=f"Threat Vector tip processing — {school} ({threat_type}, level {level})",
                metadata={
                    "call_id": call_id,
                    "school": school,
                    "threat_level": str(level),
                    "threat_type": threat_type,
                },
                confirm=False,  # In production: confirm=True with saved payment method
            )
            print(f"[{call_id}] Stripe: PaymentIntent {intent.id} created for ${amount_cents/100:.2f}")
            return {"intent_id": intent.id, "amount": amount_cents}
        else:
            # Demo mode: create a meter event (usage-based billing)
            # Shows the pattern without needing a saved card
            print(f"[{call_id}] Stripe: Demo billing event — ${amount_cents/100:.2f} for {school} tip")
            return {"demo_amount": amount_cents, "school": school}

    except stripe.StripeError as e:
        print(f"[{call_id}] WARNING: Stripe billing failed: {e}")
        return None
