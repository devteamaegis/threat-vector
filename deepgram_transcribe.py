"""
Deepgram integration — high-accuracy multilingual transcription.
Used to get a confidence score and speaker diarization for each call.
If a raw audio URL is provided by AgentPhone, Deepgram transcribes it.
Also injects emotion/sentiment markers into the transcript for Bayesian scoring.
"""
import os
import requests

DEEPGRAM_BASE = "https://api.deepgram.com/v1"


def _extract_emotion_markers(data: dict) -> list[str]:
    """
    Parse Deepgram sentiment/emotion results and return a list of marker tags
    to append to the transcript (e.g. '[tone:distressed]').
    """
    markers: list[str] = []

    # Check segment-level sentiments
    sentiments = data.get("results", {}).get("sentiments", {})
    segments = sentiments.get("segments", [])
    for seg in segments:
        sentiment = seg.get("sentiment", "")
        confidence = seg.get("sentiment_confidence", 0.0)

        if sentiment == "negative":
            if confidence > 0.85:
                markers.append("[tone:distressed]")
            elif confidence > 0.7:
                markers.append("[emotion:fear]")
        elif sentiment == "positive" and confidence > 0.7:
            markers.append("[emotion:joy]")

    # Also check utterance-level sentiment
    utterances = data.get("results", {}).get("utterances", [])
    for utt in utterances:
        sentiment = utt.get("sentiment", "")
        confidence = utt.get("sentiment_confidence", 0.0)

        if sentiment == "negative":
            if confidence > 0.85:
                if "[tone:distressed]" not in markers:
                    markers.append("[tone:distressed]")
            elif confidence > 0.7:
                if "[emotion:fear]" not in markers:
                    markers.append("[emotion:fear]")
        elif sentiment == "positive" and confidence > 0.7:
            if "[emotion:joy]" not in markers:
                markers.append("[emotion:joy]")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for m in markers:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    return unique


def transcribe_audio_url(audio_url: str, call_id: str) -> dict:
    """
    Submit audio URL to Deepgram for transcription.
    Returns: { "transcript": str, "confidence": float, "language": str, "words": list }

    The transcript string may have emotion marker tags appended
    (e.g. '[tone:distressed]') when Deepgram sentiment analysis detects
    high-confidence emotional signals. These are consumed by bayesian_scorer.
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
                "sentiment": True,
                "utterances": True,
            },
            timeout=30,
        )
        if r.status_code != 200:
            print(f"[{call_id}] WARNING: Deepgram returned {r.status_code}: {r.text[:100]}")
            return {}

        data = r.json()
        results = data.get("results", {}).get("channels", [{}])[0]
        alt = results.get("alternatives", [{}])[0]
        transcript = alt.get("transcript", "")

        # Inject emotion markers discovered by sentiment analysis
        emotion_markers = _extract_emotion_markers(data)
        if emotion_markers:
            marker_str = " ".join(emotion_markers)
            transcript = f"{transcript} {marker_str}".strip()
            print(f"[{call_id}] Deepgram sentiment: injected markers {emotion_markers}")

        return {
            "transcript": transcript,
            "confidence": alt.get("confidence", 0.0),
            "language": data.get("metadata", {}).get("detected_language", "en"),
            "words": alt.get("words", []),
            "emotion_markers": emotion_markers,
        }
    except Exception as e:
        print(f"[{call_id}] WARNING: Deepgram transcription failed: {e}")
        return {}
