"""
Deepgram integration — high-accuracy multilingual transcription.
Used to get a confidence score and speaker diarization for each call.
If a raw audio URL is provided by AgentPhone, Deepgram transcribes it.
"""
import os
import requests

DEEPGRAM_BASE = "https://api.deepgram.com/v1"

def transcribe_audio_url(audio_url: str, call_id: str) -> dict:
    """
    Submit audio URL to Deepgram for transcription.
    Returns: { "transcript": str, "confidence": float, "language": str, "words": list }
    """
    key = os.getenv("DEEPGRAM_API_KEY")
    if not key or key == "FILL_IN":
        print(f"[{call_id}] WARNING: DEEPGRAM_API_KEY not set — skipping Deepgram transcription")
        return {}

    try:
        r = requests.post(
            f"{DEEPGRAM_BASE}/listen",
            headers={
                "Authorization": f"Token {key}",
                "Content-Type": "application/json",
            },
            json={
                "url": audio_url,
                "model": "nova-3",
                "language": "multi",
                "punctuate": True,
                "diarize": True,
                "smart_format": True,
            },
            timeout=30,
        )
        if r.status_code != 200:
            print(f"[{call_id}] WARNING: Deepgram returned {r.status_code}: {r.text[:100]}")
            return {}

        data = r.json()
        results = data.get("results", {}).get("channels", [{}])[0]
        alt = results.get("alternatives", [{}])[0]
        return {
            "transcript": alt.get("transcript", ""),
            "confidence": alt.get("confidence", 0.0),
            "language": data.get("metadata", {}).get("detected_language", "en"),
            "words": alt.get("words", []),
        }
    except Exception as e:
        print(f"[{call_id}] WARNING: Deepgram transcription failed: {e}")
        return {}
