"""
Live call simulator — streams a transcript word-by-word to Supabase Realtime
so the dashboard can show a live probability bar during a demo.

Used for: demo mode, replay of recorded calls, testing.
Pushes to the `live_calls` Supabase table (must be created via migration).
Run migration_live_calls.sql in the Supabase SQL editor before using.
"""
import asyncio
import os
import re
from datetime import datetime, timezone

import requests

from bayesian_scorer import monte_carlo_score, probability_to_level, BASE_RATE

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

_DEMO_TRANSCRIPT = (
    "Hi I need to report something urgently and I'm really scared. "
    "There's a student at Westview High School who said he's going to bring a gun to school tomorrow morning. "
    "He showed me a photo of the weapon on his phone in the cafeteria. "
    "He told me specifically he is going to shoot people before first period. "
    "Multiple students have seen this and we are all terrified — he has been escalating for weeks. "
    "His name starts with J, he's in 10th grade, tall, wears a black hoodie every day. "
    "I overheard him planning this directly with someone in the parking lot. "
    "Please someone needs to stop him before tomorrow morning, this is not a joke."
)


def _headers() -> dict:
    return {
        "apikey": SUPABASE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_KEY or ''}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


def _split_sentences(text: str) -> list[str]:
    """Split transcript into sentences on .!? boundaries."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _upsert_live_call(payload: dict) -> None:
    """POST to live_calls with merge-duplicates for upsert semantics."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/live_calls",
            headers=_headers(),
            json=payload,
            timeout=5,
        )
    except Exception as e:
        print(f"[live_call_simulator] WARNING: upsert failed: {e}")


async def stream_live_call(
    call_id: str,
    transcript: str,
    school_name: str = "Demo School",
    delay_ms: int = 120,
) -> None:
    """
    Streams transcript to the live_calls Supabase table sentence-by-sentence.
    Updates Bayesian threat probability after each sentence so the dashboard
    shows a real-time climbing probability bar.

    Args:
        call_id:     Unique identifier for this simulated call.
        transcript:  The full transcript to stream.
        school_name: School name shown on the dashboard overlay.
        delay_ms:    Milliseconds between sentence pushes (default 120ms).
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        print(f"[{call_id}] WARNING: SUPABASE env vars not set — skipping live stream")
        return

    sentences = _split_sentences(transcript)
    if not sentences:
        return

    accumulated = ""

    for i, sentence in enumerate(sentences):
        accumulated = (accumulated + " " + sentence).strip()

        # Run MC with fewer sims for speed during streaming
        bayes = monte_carlo_score(accumulated, n_simulations=100)
        prob_pct = bayes["mean_probability_pct"]
        level = probability_to_level(bayes["mean_probability"])
        top_features = [d["keyword"] for d in bayes.get("top_drivers", [])][:3]

        payload = {
            "call_id": call_id,
            "words_so_far": accumulated,
            "probability_pct": prob_pct,
            "threat_level": level,
            "top_features": top_features,
            "status": "active",
            "school_name": school_name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        _upsert_live_call(payload)
        print(
            f"[{call_id}] sentence {i + 1}/{len(sentences)} "
            f"— prob={prob_pct}% level={level}/5 "
            f"triggers={top_features}"
        )

        await asyncio.sleep(delay_ms / 1000)

    # Final upsert — mark complete
    final_bayes = monte_carlo_score(transcript, n_simulations=500)
    final_pct = final_bayes["mean_probability_pct"]
    final_level = probability_to_level(final_bayes["mean_probability"])
    final_features = [d["keyword"] for d in final_bayes.get("top_drivers", [])][:3]

    # Hold on 'active' for 5s so the dashboard overlay stays visible long enough
    # to read — especially important for short single-sentence real calls.
    await asyncio.sleep(5)

    _upsert_live_call({
        "call_id": call_id,
        "words_so_far": transcript,
        "probability_pct": final_pct,
        "threat_level": final_level,
        "top_features": final_features,
        "status": "complete",
        "school_name": school_name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    print(
        f"[{call_id}] Stream complete — final prob={final_pct}% level={final_level}/5"
    )


def get_demo_transcript() -> str:
    """
    Returns a hardcoded demo transcript for a Level 5 weapon threat.
    The probability climbs dramatically sentence-by-sentence during demo playback,
    making it ideal for live showcases.
    """
    return _DEMO_TRANSCRIPT
