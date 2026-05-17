"""
Google DeepMind (Gemini) integration — second-opinion threat verification.
Uses Gemini 2.0 Flash to independently score the transcript, then we compute
a consensus with Claude's classification. If both models agree on level 4-5,
the threat is locked as CONFIRMED CRITICAL.
"""
import os
import json

GEMINI_MODEL = "gemini-2.5-flash"


def gemini_verify(transcript: str, claude_level: int, call_id: str) -> dict:
    """
    Run transcript through Gemini for independent threat assessment.
    Returns: { "gemini_level": int, "consensus": bool, "consensus_level": int, "model": str }
    """
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "FILL_IN":
        print(f"[{call_id}] WARNING: GOOGLE_API_KEY not set — skipping Gemini verification")
        return {"gemini_level": None, "consensus": False, "consensus_level": claude_level, "model": "claude-only"}

    try:
        from google import genai
        client = genai.Client(api_key=api_key)

        prompt = f"""You are a school threat assessment AI. Analyze this transcript and return ONLY a JSON object.

Transcript:
{transcript}

Return exactly:
{{
  "threat_level": <integer 1-5, where 5 is most severe>,
  "confidence": <float 0.0-1.0>,
  "reasoning": <one sentence>
}}"""

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        text = response.text.strip()

        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        data = json.loads(text)
        gemini_level = int(data.get("threat_level", 3))

        # Consensus: both models within 1 level of each other
        consensus = abs(gemini_level - claude_level) <= 1
        consensus_level = max(gemini_level, claude_level) if consensus else claude_level

        print(
            f"[{call_id}] Gemini: level {gemini_level}/5 "
            f"(Claude: {claude_level}/5) — "
            f"{'CONSENSUS' if consensus else 'DIVERGENT'} → final {consensus_level}/5"
        )

        return {
            "gemini_level": gemini_level,
            "gemini_confidence": data.get("confidence"),
            "gemini_reasoning": data.get("reasoning", ""),
            "consensus": consensus,
            "consensus_level": consensus_level,
            "model": GEMINI_MODEL,
        }

    except Exception as e:
        print(f"[{call_id}] WARNING: Gemini verification failed: {e}")
        return {"gemini_level": None, "consensus": False, "consensus_level": claude_level, "model": "claude-only"}
