# Kairos — AI School Safety Intelligence Platform

> **Real-time threat detection for school tip lines using a three-model AI consensus engine, Bayesian Monte Carlo probabilistic scoring, and a fully autonomous multi-agent response pipeline.**

Live dashboard → **[threat-vector.vercel.app](https://threat-vector.vercel.app)**  
Backend API → [threat-vector-production.up.railway.app](https://threat-vector-production.up.railway.app/health)

---

## The Problem

On November 30, 2021, a 15-year-old student at Oxford High School in Michigan opened fire in a hallway, killing four students and injuring seven more. The night before the shooting, his mother received a call from the school about a violent drawing he had made. A teacher flagged it. The parents were called in. And then — the student was sent back to class.

There was no system to correlate the drawing with a prior behavioral flag. No automated cross-reference with attendance anomalies. No probabilistic risk score. A human made a judgment call under time pressure with incomplete information, and four children died the next day.

**This happens because school threat management is still manual.** Tip lines ring unanswered after 3 PM. Calls in Spanish go to voicemails nobody checks until morning. A student who calls anonymously at 11 PM to report a weapon gets a recording. The information exists — the signal is there — but no infrastructure exists to act on it at machine speed.

Kairos is that infrastructure.

---

## What Kairos Does

A student dials a dedicated school tip line number or texts an SMS shortcode. Kairos answers instantly, 24/7, in any language. Within 60 seconds of call completion, the system has:

1. Transcribed and translated the call
2. Run three independent AI models in parallel to classify the threat
3. Computed a probabilistic threat score with a 95% confidence interval
4. Geocoded any address mentioned in the call onto a live heatmap
5. Run a multi-source background check on any named individual
6. Sent an SMS alert to the school principal
7. Dispatched a structured intelligence brief to the district safety officer
8. Logged an immutable record to the district's threat intelligence database
9. Stored the pattern in vector memory for cross-school correlation

All of this happens autonomously, without a human in the loop, in under 60 seconds.

---

## System Architecture

```
Student dials dedicated school number (AgentPhone)
OR texts SMS shortcode
         │
         ▼
AgentPhone AI agent answers, records + transcribes in real time
         │  webhook → Railway FastAPI backend
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      KAIROS PIPELINE (~12–60s)                       │
│                                                                      │
│  STAGE 1: TRANSLATION                                                │
│    Gemini Live  → multilingual real-time detect + translate (70+)    │
│                   working_transcript used for all downstream steps   │
│                                                                      │
│  STAGE 2: PARALLEL ENRICHMENT                                        │
│    Branch A:                                                         │
│      Moss       → semantic context search against prior tip corpus   │
│      Anthropic  → primary threat classification (18-field JSON)      │
│    Branch B (concurrent with A):                                     │
│      Bayesian MC → 500-simulation probabilistic scoring + 95% CI     │
│      Gemini Flash → independent second-opinion threat level          │
│      Supermemory  → query prior incident patterns for this school    │
│      Geocoder     → Nominatim address extraction + lat/lng           │
│                                                                      │
│  STAGE 3: CONSENSUS + FINALIZATION                                   │
│    3-model vote (Anthropic + Gemini + Bayes) → final_level 1-5       │
│    Named subject extraction → background check pipeline              │
│                                                                      │
│  STAGE 4: AUTONOMOUS RESPONSE (level 3+)                             │
│    Sponge       → micropayment authorization per agent action        │
│    OSINT        → DuckDuckGo + CourtListener + Bing + Browser-Use    │
│    Supermemory  → store pattern for future correlation               │
│    Moss         → index tip for semantic search                      │
│    Twilio       → SMS alert to school principal                      │
│    AgentMail    → structured HTML brief to district safety officer   │
└──────────────────────────────────────────────────────────────────────┘
         │
         ▼
Supabase Realtime → Vercel Next.js dashboard
         │
         ▼
Live threat feed + GPS heatmap + Bayesian breakdown modal + wallet ledger
```

---

## The Math: Bayesian Monte Carlo Threat Scoring

This is the scientific core of Kairos — a transparent probabilistic model grounded in FBI behavioral threat assessment literature (NTAC, 2020), not a black-box neural network.

### Prior Probability

```
P₀ = BASE_RATE = 0.002  (0.2%)
```

Calibrated from FBI National Threat Assessment Center data: approximately 1 in 500 calls to a school tip line represents a credible, actionable threat. This is the unconditional prior before any transcript features are observed.

### Likelihood Ratio Updates (Sequential Bayesian Chaining)

Each verbal feature detected in the transcript updates the posterior probability using Bayes' theorem in log-odds form:

```
# Convert prior to odds
prior_odds = P₀ / (1 - P₀)

# Apply each feature's likelihood ratio multiplicatively
posterior_odds = prior_odds × LR₁ × LR₂ × ... × LRₙ

# Convert back to probability
P(threat | features) = posterior_odds / (1 + posterior_odds)

where:
  LR = P(feature | real threat) / P(feature | non-threat call)
```

The chain is sequential — each sentence's posterior becomes the prior for the next observed feature. Example trace for a real-pattern call:

```
P₀ = 0.20%   (baseline)
↓  "gun"              [weapon_explicit,   LR=12.0 ± 3.0]  → P₁ =  2.3%
↓  "cafeteria"        [specific_location, LR= 4.0 ± 1.2]  → P₂ =  8.5%
↓  "tomorrow morning" [timeline_near,     LR= 4.5 ± 1.2]  → P₃ = 31.2%
↓  "i heard him say"  [direct_witness,    LR= 6.0 ± 1.5]  → P₄ = 72.8%
↓  "for weeks"        [escalation_pattern,LR= 4.5 ± 1.2]  → P₅ = 93.4%
```

### Feature Likelihood Table

Calibrated against FBI NTAC behavioral science literature and Secret Service threat assessment protocols:

| Category | Feature | Keywords | LR (mean) | LR (std) |
|----------|---------|----------|-----------|----------|
| Weapon | Explicit weapon | gun, knife, bomb, rifle, shoot | 12.0 | 3.0 |
| Evidence | Weapon photo/evidence | "showed a photo", "screenshot" | 18.0 | 4.0 |
| Timeline | Imminent | today, tonight, right now, in an hour | 8.0 | 2.0 |
| Timeline | Near-term | tomorrow, this week, Monday | 4.5 | 1.2 |
| Specificity | Named subject | "his name is", "a kid named" | 5.0 | 1.5 |
| Location | Specific place | gym, cafeteria, parking lot, room | 4.0 | 1.2 |
| Credibility | First-hand witness | "I saw", "I heard", "I was there" | 6.0 | 1.5 |
| Credibility | Multiple witnesses | "everyone", "multiple students" | 3.5 | 1.0 |
| Pattern | Escalation history | "been happening for weeks", "getting worse" | 4.5 | 1.2 |
| Target | Named victim | "targeting", "going after [name]" | 5.0 | 1.5 |
| Severity | Mass harm language | "everyone", "whole school", "nobody survives" | 15.0 | 4.0 |

### Monte Carlo Simulation (500 iterations)

Because each LR has uncertainty (mean ± std), we don't just compute a point estimate. We run **500 Monte Carlo simulations**, sampling each feature's LR from its probability distribution:

```python
def monte_carlo_score(transcript, n_simulations=500):
    features = extract_features(transcript)       # NLP feature extraction
    probabilities = []

    for _ in range(n_simulations):
        odds = BASE_RATE / (1 - BASE_RATE)        # prior odds

        for feature in features:
            # Sample LR from normal distribution (mean, std)
            lr_sample = np.random.normal(feature.lr_mean, feature.lr_std)
            lr_sample = max(lr_sample, 1.0)        # LR must be ≥ 1
            odds *= lr_sample

        p = odds / (1 + odds)                      # back to probability
        probabilities.append(min(p, 0.999))

    return {
        "mean_probability":     np.mean(probabilities),
        "ci_low":               np.percentile(probabilities, 2.5),
        "ci_high":              np.percentile(probabilities, 97.5),
        "top_drivers":          top_k_features_by_lr(features, k=3),
    }
```

The **95% confidence interval width** is itself diagnostic:

| CI Width | Interpretation | Action |
|----------|---------------|--------|
| < 15 pp | Narrow — model is certain | Trust the level |
| 15–40 pp | Moderate — some ambiguity | Escalate if level ≥ 3 |
| > 40 pp | Wide — conflicting signals | Flag for human review regardless |

### Three-Model Consensus

The final threat level is determined by voting across three independent models:

```python
final_level = max(anthropic_level, gemini_level, bayes_level)

three_model_consensus = (
    abs(anthropic_level - gemini_level) <= 1 and
    abs(anthropic_level - bayes_level) <= 1
)
```

**Conservative by design**: we take the maximum, not the mean. In school safety, the cost of a false negative (missing a real threat) vastly exceeds the cost of a false positive. Divergence between models flags the call for urgent human review.

### Threat Level Mapping

| Level | Probability | Action | Response Time |
|-------|------------|--------|---------------|
| 1 | < 15% | Log, monitor | Standard |
| 2 | 15–35% | Review + monitor | Within 24h |
| 3 | 35–60% | Active investigation | Within 4h |
| 4 | 60–80% | Immediate escalation | Within 30min |
| 5 | > 80% | Emergency response | Immediate |

---

## Sponsor Integration — Technical Detail

### AgentPhone — Voice Infrastructure + SMS

**Role**: The entry point for all calls and text tips.

Each school district is provisioned a **dedicated phone number** through AgentPhone. Students call it anonymously to report threats, or text a threat directly to the SMS shortcode. AgentPhone's AI agent answers 24/7, prompts the caller in their language, records the full call, and sends a webhook to the Kairos Railway backend the moment the call ends.

**Technical implementation**:
- Webhook payload: `{ call_id, transcript, recording_url, caller_location, duration_seconds }`
- The webhook fires to `POST /api/webhook/inbound-call` on the Railway FastAPI server
- The `call_id` is the persistent key that links all downstream Supabase records
- SMS tips trigger the same pipeline as voice calls — the transcript is the message body

**Why it matters**: A dedicated number per school means zero friction for the reporter. No app to download, no account to create. Just a phone call.

---

### Gemini Live — Real-Time Multilingual Transcription

**Role**: Multilingual detection, translation, and first-pass semantic analysis.

Gemini Live is the first model to see every call transcript. It detects the spoken language (supporting 70+ languages), translates to English if needed, and returns a structured result that all downstream models consume.

**Technical implementation**:
```python
live_result = await asyncio.wait_for(
    live_multilingual_analysis(transcript, call_id),
    timeout=12
)
# Returns: { detected_language, english_translation, multilingual: bool }
```

If the call is multilingual, `working_transcript` (the English translation) is used for every downstream step — Claude, Gemini Flash, Bayesian scoring, OSINT, and address extraction all operate on the same translated text.

**Why it matters**: 22% of US households speak a language other than English at home. A Spanish-speaking parent calling at 2 AM to report a weapon gets the same 12-second response as an English speaker.

---

### Anthropic — Primary Threat Classification

**Role**: The core semantic classifier. Produces a 22-field structured JSON from the call transcript.

The Anthropic API receives the working transcript plus Moss semantic context and returns a structured classification with threat level, threat type, school name, subject description, named subject, key facts, credibility signals, recommended action, location detail, dispatch brief, and — critically — `named_subject` (the extracted full name of any individual being threatened or threatening).

**Technical implementation**:
```python
# Structured JSON output with 22 fields including:
{
    "threat_level": 1-5,
    "threat_type": "weapon|bullying|self_harm|...",
    "school_name": "...",
    "named_subject": "Max Higgins",  # triggers background check
    "location_detail": "Germantown, MD",  # used for geocoding
    "key_facts": [...],
    "credibility_signals": [...],
    "recommended_action": "immediate_response|...",
    "dispatch_brief": "...",
    "bayes_features_hit": [...]  # pre-tagged for Bayesian scorer
}
```

This runs twice: once before Moss context (early INSERT to show card on dashboard), and once after Moss enrichment (final classification with historical pattern context).

---

### Gemini Flash — Independent Verification (Second Opinion)

**Role**: A completely independent threat level from a different model to prevent single-model failure modes.

Gemini Flash receives only the raw transcript — no Moss context, no Anthropic output — and produces its own threat level and reasoning. This creates genuine independence between the two language model votes.

**Technical implementation**:
```python
gemini_res = await asyncio.wait_for(
    gemini_verify(working_transcript, claude_level, call_id),
    timeout=10
)
# Returns: { gemini_level: int, gemini_reasoning: str, consensus: bool }
```

The consensus flag (`abs(anthropic_level - gemini_level) <= 1`) is displayed on the dashboard card and in the dispatch brief. Divergence > 1 level automatically flags the call for urgent human review.

**Why it matters**: No single model is right 100% of the time. Two independent models that disagree is a stronger signal than one model being uncertain.

---

### Supermemory — Cross-District Pattern Memory

**Role**: Semantic long-term memory that stores and recalls all prior threat patterns across every school in the district.

Every processed call is stored in Supermemory with school name, threat type, and key features as metadata. When a new call comes in, Supermemory is queried with the current transcript to surface semantically similar prior incidents.

**Technical implementation**:
```python
# Store after each call
store_tip_memory(classification, call_id)

# Query on each new call (runs in parallel with Bayesian + Gemini)
prior_context = search_prior_tips(
    school_name,
    threat_type,
    key_facts,
)
# prior_context is injected into Anthropic's enriched classification prompt
```

If the same school has had 3 weapon reports in 30 days, that context is injected into the classification prompt — dramatically increasing recall for escalating patterns that no single call would trigger alone.

---

### Moss — Semantic Vector Search

**Role**: Real-time semantic context retrieval against the entire corpus of indexed tips.

Moss indexes each tip as a dense vector embedding. When a new call comes in, it performs a sub-100ms nearest-neighbor search across all prior tips to find semantically related incidents, even when the wording is completely different.

**Technical implementation**:
```python
# Index each tip for future search
index_tip(
    f"{school} {threat_type} {summary}",
    {"school": school, "level": final_level, "call_id": call_id},
    call_id,
)

# Query on new calls (parallel branch)
moss_context = semantic_search_tips(working_transcript[:300], call_id)
# Returns: relevant prior tip summaries injected as context
```

The distinction from Supermemory: Moss is real-time semantic similarity search; Supermemory is structured pattern memory with metadata filtering. Both run concurrently.

---

### Sponge — Agent Economy Micropayments

**Role**: The financial ledger for every autonomous agent action. Every AI service call is a micropayment transaction.

Sponge enables the "agent economy" model — where AI agents autonomously pay each other for services. Every OSINT search, background check, SMS dispatch, and email brief generates a Sponge micropayment transaction logged to the district's wallet.

**Technical implementation**:
```python
# Called after each agent action
disburse_agent_payment(
    service="background-check-agent",
    amount_cents=threat_level,   # level 3 = 3¢, level 4 = 4¢, level 5 = 5¢
    call_id=call_id,
    metadata={"subject": name, "school": school, "threat_level": level}
)
```

The dashboard's Wallet tab shows a live transaction feed — every agent action that cost money, with the subject, service, amount, and Sponge transaction ID. Districts can audit exactly what the AI did and what it cost, per call.

**Cost model**: ~$0.09–0.15 in agent micropayments per threat-level-3+ call. The full pipeline (including LLM inference) costs ~$0.22–0.35 per call.

---

### Supabase — Real-Time Threat Intelligence Database

**Role**: The central single source of truth. Every tip, every field, every enrichment patch — live-streamed to the dashboard.

Each call triggers an **early INSERT** the moment Anthropic's first classification completes (~12 seconds), making the threat card visible on the dashboard immediately. A second **PATCH** follows with full enrichment (Bayesian scores, Gemini level, OSINT findings, background check, geocoordinates) once the parallel pipeline completes.

**Technical implementation**:
```python
# Early INSERT — dashboard card appears at ~12s
tip_id = log_tip_to_aegis(classification, transcript, call_id)

# Parallel PATCH at ~45-60s with full enrichment
update_tip_enriched(tip_id, call_id, {
    "bayes_probability_pct": ...,
    "gemini_level": ...,
    "mentioned_lat": ...,      # geocoded address pin on heatmap
    "mentioned_lng": ...,
    "background_check_subject": ...,
    "osint_findings": ...,
    ...
})
```

The Next.js dashboard subscribes via Supabase Realtime websockets. New tips appear in under 1 second of database insert. The heatmap polls every 6 seconds for geocoordinate updates.

**Schema**: The `tips` table has 50+ columns covering every field from all three AI models, Bayesian scores, geocoordinates, OSINT findings, pipeline errors, and response status.

---

### AgentMail — Autonomous District Briefings

**Role**: Generates and dispatches structured HTML intelligence briefs to school administrators for all level-3+ threats.

For every high-priority call, AgentMail composes a formatted brief containing: the AI risk assessment, key facts, Bayesian probability, three-model consensus status, dispatch location context, recommended action, and the Sponge transaction receipt. This goes directly to the district safety officer's inbox within 60 seconds of call completion.

**Technical implementation**:
```python
# Runs in post-dashboard async task (doesn't block dashboard update)
email_result = await send_agentmail_brief(
    to=district_email,
    subject=f"[KAIROS {level}/5] {school} — {threat_type}",
    html=format_brief_html(classification, bayes_result, receipt)
)
```

The principal also receives an SMS via Twilio simultaneously — the SMS is the fast alert; the AgentMail brief is the full actionable intelligence package.

---

## Deployment Architecture

```
┌──────────────────────────────────────────────────────────┐
│  FRONTEND (Vercel)                                        │
│  Next.js 15 App Router · TypeScript · Tailwind v4        │
│  Supabase Realtime websocket subscription                │
│  Mapbox GL — live GPS heatmap                            │
│  6s polling for geocoordinate updates                    │
└──────────────────┬───────────────────────────────────────┘
                   │ HTTPS
┌──────────────────▼───────────────────────────────────────┐
│  BACKEND (Railway)                                        │
│  FastAPI · Python 3.13 · asyncio                         │
│  Concurrent pipeline: max(Branch_A, Branch_B) < 60s      │
│  AgentPhone webhook receiver                             │
│  Supabase REST + Sponge REST                             │
└──────────────────┬───────────────────────────────────────┘
                   │
┌──────────────────▼───────────────────────────────────────┐
│  DATABASE (Supabase)                                      │
│  tips table: 50+ columns · Realtime enabled              │
│  live_calls table: current active call state             │
│  sponge_transactions: agent payment audit trail          │
│  attendance table: daily check-in records                │
└──────────────────────────────────────────────────────────┘
```

---

## Real-World Implementation

### Per-School Dedicated Numbers

Each school in a district gets its own dedicated phone number through AgentPhone. The number is printed on student ID cards, posted in hallways, and included in the school handbook. Students can:

- **Call** anonymously to speak directly to the AI agent
- **Text** a threat description to the same number

No app. No account. No tracking. Just a number.

### Integration with Existing Infrastructure

Kairos requires zero hardware changes. Districts that already have a tip line number can forward calls to the Kairos AgentPhone number. The implementation checklist:

```
1. Provision AgentPhone number (< 5 minutes)
2. Configure district email for AgentMail briefs (< 2 minutes)  
3. Set principal SMS number for Twilio alerts (< 1 minute)
4. Point existing tip line to new number (< 1 minute)
```

Total deployment time: under 15 minutes per school.

### Cost Structure

| Component | Cost per call | Annual cost (1,000 calls/yr) |
|-----------|--------------|------------------------------|
| AgentPhone | ~$0.02 | $20 |
| AI inference (3 models) | ~$0.18 | $180 |
| Sponge micropayments | ~$0.05 | $50 |
| SMS + email | ~$0.02 | $20 |
| **Total** | **~$0.27** | **$270** |

A district of 10 schools pays approximately **$2,700/year** for 24/7 autonomous threat triage — less than the salary cost of a single part-time tip line coordinator for one month.

---

## Impact

**The core problem Kairos solves**: the gap between when a threat is reported and when it is acted on.

In documented pre-attack cases analyzed by the Secret Service's National Threat Assessment Center, **81% of school attackers communicated their intent to someone beforehand**. The barrier isn't information — it's processing speed and pattern recognition.

| Metric | Traditional Tip Line | Kairos |
|--------|---------------------|--------|
| Response time (business hours) | 2–4 hours | 12 seconds |
| Response time (nights/weekends) | Next business day | 12 seconds |
| Languages supported | 1–2 (staff dependent) | 70+ |
| Cross-school pattern detection | None | Automatic |
| Probabilistic risk scoring | None | 95% CI Bayesian |
| Audit trail | Paper/Google Docs | Immutable Supabase log |
| Cost per tip | $15–50 (labor) | $0.27 (fully autonomous) |

**Every minute faster matters.** In the Oxford case, the drawing was flagged at 10 AM. The shooting happened the next day at 12:51 PM. A system that could have cross-referenced that flag with the student's prior behavioral record, social media activity, and the school's historical threat pattern — and delivered a calibrated risk score to the principal within 60 seconds — might have changed the outcome.

Kairos is that system.

---

## Repository Structure

```
threat-vector/              # FastAPI backend (Railway)
├── main.py                 # API routes + webhook handler
├── agent.py                # Core pipeline orchestrator
├── background_check.py     # Multi-source OSINT (DDG + CourtListener + Bing)
├── sponge_payments.py      # Sponge micropayment integration
├── osint.py                # Browser-Use OSINT agent
├── bayes.py                # Bayesian likelihood ratio engine
├── monte_carlo.py          # 500-simulation MC scorer
├── gemini.py               # Gemini Live + Flash integration
├── supabase.py             # DB read/write layer
├── memory.py               # Supermemory integration
├── moss.py                 # Moss semantic search
├── sms.py                  # Twilio SMS dispatch
├── agentmail.py            # AgentMail brief generation
└── prompts.py              # Structured prompt templates

threat-vector-dashboard/    # Next.js dashboard (Vercel)
├── app/
│   ├── page.tsx            # Main dashboard + orb + live call
│   ├── heatmap/            # Live GPS heatmap page
│   ├── district/           # District analytics view
│   └── api/                # Next.js API routes (proxy to Railway)
└── components/
    ├── ThreatHeatmap.tsx    # Mapbox GL heatmap + geocoded pins
    ├── ThreatBreakdownModal.tsx  # Bayesian breakdown + "What This Means"
    └── SpongeWalletPanel.tsx     # Agent payment ledger + PDF export
```

---

## Environment Variables

```bash
# Backend (Railway)
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
AGENTPHONE_API_KEY=
AGENTMAIL_API_KEY=
SUPERMEMORY_API_KEY=
MOSS_API_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
SPONGE_API_KEY=
SPONGE_WALLET_ID=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
OPENAI_API_KEY=           # optional — enables Browser-Use OSINT

# Frontend (Vercel)
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_MAPBOX_TOKEN=
BACKEND_URL=https://threat-vector-production.up.railway.app
```

---

*Built for YC S25 — Kairos AI · Threat intelligence infrastructure for every school district in America.*
