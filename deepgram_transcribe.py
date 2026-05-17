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

    def add_marker(marker: str):
        if marker not in markers:
            markers.append(marker)

    def markers_from_text(value: str):
        text = value.lower()
        if any(w in text for w in ("fear", "afraid", "scared", "terrified", "distress", "worry", "anxious")):
            add_marker("[emotion:fear]")
        if any(w in text for w in ("panic", "panicked", "urgent", "emergency", "immediate", "danger")):
            add_marker("[tone:panicked]")
            add_marker("[urgency:high]")
        if any(w in text for w in ("laugh", "joke", "humor", "amused", "happy", "joy")):
            add_marker("[emotion:joy]")
        if any(w in text for w in ("uncertain", "hesitant", "unsure", "confused")):
            add_marker("[emotion:uncertain]")

    # Check segment-level sentiments
    sentiments = data.get("results", {}).get("sentiments", {})
    segments = sentiments.get("segments", [])
    for seg in segments:
        sentiment = seg.get("sentiment", "")
        confidence = seg.get("sentiment_confidence", 0.0)

        if sentiment == "negative":
            if confidence > 0.85:
                add_marker("[tone:distressed]")
            elif confidence > 0.7:
                add_marker("[emotion:fear]")
        elif sentiment == "positive" and confidence > 0.7:
            add_marker("[emotion:joy]")
        markers_from_text(str(seg.get("text", "")))

    # Also check utterance-level sentiment
    utterances = data.get("results", {}).get("utterances", [])
    for utt in utterances:
        sentiment = utt.get("sentiment", "")
        confidence = utt.get("sentiment_confidence", 0.0)

        if sentiment == "negative":
            if confidence > 0.85:
                add_marker("[tone:distressed]")
            elif confidence > 0.7:
                add_marker("[emotion:fear]")
        elif sentiment == "positive" and confidence > 0.7:
            add_marker("[emotion:joy]")
        markers_from_text(str(utt.get("transcript", "") or utt.get("text", "")))

    # Deepgram topics/intents can surface emotional or urgency cues directly.
    for topic in data.get("results", {}).get("topics", {}).get("segments", []):
        for detected in topic.get("topics", []):
            markers_from_text(str(detected.get("topic", "")))
        markers_from_text(str(topic.get("text", "")))

    for intent in data.get("results", {}).get("intents", {}).get("segments", []):
        for detected in intent.get("intents", []):
            markers_from_text(str(detected.get("intent", "")))
        markers_from_text(str(intent.get("text", "")))

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
                "topics": True,
                "intents": True,
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
