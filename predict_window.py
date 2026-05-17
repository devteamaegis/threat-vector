"""
Predictive threat window — estimates when a threat is most likely to occur
based on timeline keywords in the transcript.

Works alongside the Bayesian scorer's timeline features to give human-readable
time estimates that go directly to the dashboard and dispatch brief.
"""
import re
from datetime import datetime


# ── Timeline signal patterns ──────────────────────────────────────────────────
# Each entry: (regex_pattern, human_readable_window, priority)
# Higher priority = matched first when multiple signals are present.

_TIMELINE_PATTERNS: list[tuple[str, str, int]] = [
    # Immediate — highest priority
    (r"\bright\s+now\b",                        "Within hours — IMMEDIATE",                             100),
    (r"\bhappening\s+now\b",                    "Within hours — IMMEDIATE",                             100),
    (r"\bgoing\s+to\s+do\s+it\s+now\b",         "Within hours — IMMEDIATE",                             100),
    (r"\btoday\b",                              "Within hours — IMMEDIATE",                              90),
    (r"\bthis\s+morning\b",                     "Within hours — IMMEDIATE",                              90),
    (r"\bthis\s+afternoon\b",                   "Today after school hours (2:30–6pm)",                   85),
    (r"\bafter\s+school\b",                     "Today after school hours (2:30–6pm)",                   85),
    (r"\btonight\b",                            "Today after school hours (2:30–6pm)",                   80),

    # Tomorrow
    (r"\btomorrow\s+morning\b",                 "Tomorrow morning arrival (7–8:30am)",                   75),
    (r"\bbefore\s+school\s+tomorrow\b",         "Tomorrow morning arrival (7–8:30am)",                   75),
    (r"\btomorrow\b",                           "Within 24 hours",                                        70),

    # Day of week references
    (r"\bthis\s+friday\b",                      "Friday (arrival or dismissal window)",                   65),
    (r"\bfriday\b",                             "Friday (arrival or dismissal window)",                   60),
    (r"\bmonday\b",                             "Within 7 days",                                          55),
    (r"\bnext\s+week\b",                        "Within 7 days",                                          50),
    (r"\bthis\s+week\b",                        "Within 7 days",                                          50),
    (r"\bfew\s+days\b",                         "Within 7 days",                                          45),

    # Vague — lowest priority
    (r"\bsoon\b",                               "Unspecified — monitor closely",                          20),
    (r"\bat\s+some\s+point\b",                  "Unspecified — monitor closely",                          15),
    (r"\bgoing\s+to\b",                         "Unspecified — monitor closely",                          10),
]

_COMPILED_PATTERNS = [(re.compile(pat, re.IGNORECASE), window, priority)
                      for pat, window, priority in _TIMELINE_PATTERNS]


def predict_threat_window(transcript: str, classification: dict) -> dict:
    """
    Analyze transcript for time references and return a predicted threat window.

    Also checks classification.get('timeline') for additional signals from Claude.

    Returns:
        {
            "window": str,          — human-readable threat window
            "confidence": str,      — "high" | "medium" | "low"
            "raw_signals": list[str]
        }
    """
    combined_text = transcript

    # Fold in any timeline string from Claude's classification
    cl_timeline = classification.get("timeline") or ""
    if cl_timeline:
        combined_text = f"{combined_text} {cl_timeline}"

    # Also check ai_summary for timeline signals
    ai_summary = classification.get("ai_summary") or ""
    if ai_summary:
        combined_text = f"{combined_text} {ai_summary}"

    combined_lower = combined_text.lower()

    # Collect all matching signals
    matched: list[tuple[str, int]] = []   # (window, priority)
    raw_signals: list[str] = []

    for compiled_re, window, priority in _COMPILED_PATTERNS:
        hit = compiled_re.search(combined_lower)
        if hit:
            signal_text = combined_lower[max(0, hit.start() - 10):hit.end() + 10].strip()
            raw_signals.append(signal_text)
            matched.append((window, priority))

    if not matched:
        return {
            "window": "Unknown — insufficient timeline signals",
            "confidence": "low",
            "raw_signals": [],
        }

    # Pick the highest-priority (most specific) window
    matched.sort(key=lambda x: x[1], reverse=True)
    best_window = matched[0][0]

    # Determine confidence: multiple distinct signals → high
    unique_windows = {w for w, _ in matched}
    if len(matched) >= 3 or (len(unique_windows) >= 2 and matched[0][1] >= 70):
        confidence = "high"
    elif len(matched) >= 2 or matched[0][1] >= 60:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "window": best_window,
        "confidence": confidence,
        "raw_signals": list(dict.fromkeys(raw_signals))[:5],  # deduplicate, cap at 5
    }
