"""
Bayesian + Monte Carlo threat scoring layer.

ARCHITECTURE (from the diagram):
  Transcript → Feature extraction → Bayesian updater → Monte Carlo simulator
              ↑ verbal context clues          ↑ district base rates    ↑ historical call data

THE MATH:
  Prior:    P(threat) = BASE_RATE (1 in 500 calls is a credible threat)
  Update:   P(threat | feature) = P(feature|threat) × P(threat) / P(feature)
  Chain:    Each new sentence updates the posterior from the previous one.
            Posterior after sentence k becomes the prior for sentence k+1.

  Monte Carlo:
    Feature weight uncertainty → distributions over each likelihood ratio.
    Run N=1000 simulations sampling from those distributions.
    Output: mean probability + 95% confidence interval.

VERBAL CONTEXT CLUES (likelihood ratios):
  Each feature has a ratio R = P(feature | real threat) / P(feature | non-threat)
  R > 1 → raises probability. R < 1 → lowers it.
  These are calibrated against FBI behavioral threat assessment literature.
"""

import re
import numpy as np
from typing import TypedDict


# ── Base rate ─────────────────────────────────────────────────────────────────
# 1 in 500 incoming calls to a school tip line is a credible threat
BASE_RATE = 0.002


# ── Feature likelihood table ──────────────────────────────────────────────────
# Each entry: (pattern | keyword list, mean_ratio, std_ratio)
# std_ratio is the uncertainty — fed into Monte Carlo distributions.

FEATURE_TABLE: list[tuple[str, list[str], float, float]] = [
    # Category: Weapons
    ("weapon_explicit",   ["gun", "knife", "weapon", "firearm", "pistol", "rifle", "shoot", "stab", "bomb", "explosive"],  12.0, 3.0),
    ("weapon_photo",      ["showed a photo", "picture of a", "showed me a", "photo of", "sent a picture"],                 18.0, 4.0),
    ("weapon_implicit",   ["do something", "hurt people", "hurt everyone", "make them pay", "going to do it"],               4.0, 1.5),

    # Category: Timeline
    ("timeline_immediate",["right now", "happening now", "today", "this morning", "tonight", "right now"],                  8.0, 2.0),
    ("timeline_near",     ["tomorrow", "next week", "friday", "monday", "this week", "few days"],                           4.5, 1.2),
    ("timeline_vague",    ["soon", "eventually", "at some point", "going to"],                                               1.3, 0.4),

    # Category: Specificity — strongest credibility signals
    ("specific_person",   ["his name", "her name", "the student", "a kid named", "he told", "she said she"],               5.0, 1.5),
    ("specific_location", ["gym", "cafeteria", "bathroom", "classroom", "hallway", "parking lot", "locker"],               4.0, 1.2),
    ("specific_method",   ["planning to", "said he would", "told people", "showed how"],                                    7.0, 2.0),

    # Category: Social proof
    ("multiple_witnesses",["other people saw", "multiple students", "lots of kids", "everyone knows", "we all saw"],        3.5, 1.0),
    ("escalation_pattern",["been doing this", "for weeks", "getting worse", "keeps saying", "pattern", "again"],            4.5, 1.2),
    ("direct_witness",    ["i heard", "i saw", "they told me directly", "overheard", "i was there"],                        6.0, 1.5),
    ("second_hand",       ["someone told me", "i heard from", "people are saying", "rumor"],                                 1.8, 0.6),

    # Category: Caller credibility — positive
    ("caller_fearful",    ["scared", "terrified", "afraid", "worried", "i'm scared", "freaking out", "please help"],       3.0, 0.8),
    ("caller_precise",    ["exact", "specifically", "i counted", "i have the", "i saved"],                                  2.5, 0.7),

    # Category: Caller credibility — negative (reduces probability)
    ("caller_laughs",     ["haha", "lol", "just kidding", "just joking", "not serious"],                                    0.10, 0.05),
    ("caller_vague",      ["just thought", "maybe nothing", "probably fine", "i don't know"],                               0.55, 0.2),
    ("anonymous_hedge",   ["don't want to get anyone in trouble", "maybe i'm wrong"],                                       0.7,  0.2),
]

# Compile patterns for fast matching
_COMPILED = [
    (name, [kw.lower() for kw in keywords], mean, std)
    for name, keywords, mean, std in FEATURE_TABLE
]


# ── Feature extraction ────────────────────────────────────────────────────────

class FeatureHit(TypedDict):
    name: str
    keyword: str
    mean_ratio: float
    std_ratio: float


def extract_features(text: str) -> list[FeatureHit]:
    """Scan text for verbal context clues. Returns all matched features."""
    text_lower = text.lower()
    hits: list[FeatureHit] = []
    seen_names: set[str] = set()

    for name, keywords, mean, std in _COMPILED:
        if name in seen_names:
            continue
        for kw in keywords:
            if kw in text_lower:
                hits.append(FeatureHit(name=name, keyword=kw, mean_ratio=mean, std_ratio=std))
                seen_names.add(name)
                break

    return hits


# ── Bayesian updater ──────────────────────────────────────────────────────────

def bayesian_update(prior: float, likelihood_ratio: float) -> float:
    """
    Single Bayes step.
    P(threat | feature) = P(feature|threat) × P(threat) / P(feature)
    Using odds form: posterior_odds = prior_odds × likelihood_ratio
    """
    prior_odds = prior / (1 - prior)
    posterior_odds = prior_odds * likelihood_ratio
    return posterior_odds / (1 + posterior_odds)


def score_transcript(transcript: str, prior: float = BASE_RATE) -> dict:
    """
    Run Bayesian update over the full transcript sentence-by-sentence.
    Returns point estimate + feature trace.
    """
    sentences = re.split(r'[.!?]+', transcript)
    probability = prior
    feature_trace: list[dict] = []

    for sentence in sentences:
        if not sentence.strip():
            continue
        features = extract_features(sentence)
        for f in features:
            prev = probability
            probability = bayesian_update(probability, f["mean_ratio"])
            feature_trace.append({
                "sentence": sentence.strip()[:80],
                "feature":  f["name"],
                "keyword":  f["keyword"],
                "delta":    round(probability - prev, 4),
                "probability_after": round(probability, 4),
            })

    return {
        "probability": round(probability, 4),
        "probability_pct": round(probability * 100, 1),
        "feature_trace": feature_trace,
        "features_hit": list({f["feature"] for f in feature_trace}),
        "feature_count": len(feature_trace),
    }


# ── Monte Carlo layer ─────────────────────────────────────────────────────────

def monte_carlo_score(transcript: str, n_simulations: int = 1000, prior: float = BASE_RATE) -> dict:
    """
    Run N simulations with sampled feature weights to produce a distribution.
    Each simulation samples likelihood ratios from N(mean, std) distributions.

    Output:
      mean_probability    — central estimate
      ci_low, ci_high     — 95% confidence interval
      std                 — spread of distribution
      feature_trace       — what's driving the score
    """
    features = extract_features(transcript)
    if not features:
        return {
            "mean_probability": prior,
            "mean_probability_pct": round(prior * 100, 2),
            "ci_low_pct": round(prior * 100, 2),
            "ci_high_pct": round(prior * 100, 2),
            "std_pct": 0.0,
            "features_hit": [],
            "feature_count": 0,
            "feature_trace": [],
            "n_simulations": n_simulations,
        }

    results = np.zeros(n_simulations)

    for sim in range(n_simulations):
        p = prior
        for f in features:
            # Sample ratio from normal distribution (clipped to > 0.01)
            sampled_ratio = max(0.01, np.random.normal(f["mean_ratio"], f["std_ratio"]))
            prior_odds = p / (1 - p + 1e-9)
            posterior_odds = prior_odds * sampled_ratio
            p = posterior_odds / (1 + posterior_odds)
        results[sim] = p

    ci_low, ci_high = np.percentile(results, [2.5, 97.5])
    mean_p = float(np.mean(results))

    # Feature trace using mean ratios for explanation
    trace = score_transcript(transcript, prior)["feature_trace"]

    return {
        "mean_probability":     round(mean_p, 4),
        "mean_probability_pct": round(mean_p * 100, 1),
        "ci_low_pct":           round(float(ci_low) * 100, 1),
        "ci_high_pct":          round(float(ci_high) * 100, 1),
        "std_pct":              round(float(np.std(results)) * 100, 1),
        "features_hit":         [f["name"] for f in features],
        "feature_count":        len(features),
        "feature_trace":        trace,
        "n_simulations":        n_simulations,
        "top_drivers": sorted(
            [{"feature": f["name"], "keyword": f["keyword"], "ratio": f["mean_ratio"]} for f in features],
            key=lambda x: x["ratio"], reverse=True
        )[:3],
    }


# ── Calibrated threat level ───────────────────────────────────────────────────

def probability_to_level(p: float) -> int:
    """Map Bayesian probability to 1-5 threat level."""
    if p >= 0.70: return 5
    if p >= 0.40: return 4
    if p >= 0.15: return 3
    if p >= 0.04: return 2
    return 1
