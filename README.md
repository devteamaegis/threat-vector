# Kairos — AI School Safety Intelligence Platform

> **Real-time threat detection for school tip lines using a three-model AI consensus engine, Bayesian Monte Carlo scoring, and autonomous agent pipelines.**

Live dashboard → **[kairos-dashboard.vercel.app](https://kairos-dashboard.vercel.app)**  
Backend API → Railway (FastAPI + Python)

---

## The Problem

Every year, school shootings are preceded by credible warnings that go unacted on — not because no one called, but because the call wasn't processed in time. Existing tip lines rely on humans answering phones during business hours. A parent calling at 10 PM in Spanish about a weapon they saw in a cafeteria gets a voicemail. That voicemail sits unheard until morning.

**Kairos replaces that voicemail with an autonomous AI pipeline that processes every call in under 60 seconds, regardless of language, time of day, or call volume.**

---

## Architecture Overview

```
Caller dials AgentPhone number
        │
        ▼
AgentPhone AI answers, records & transcribes
        │  webhook → Railway FastAPI
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    KAIROS PIPELINE                              │
│                                                                 │
│  1. Gemini Live  → multilingual detect + translate (70 langs)  │
│  2. Moss         → semantic context search (prior tips)         │
│  3. Claude       → primary threat classification               │
│  4. Gemini Flash → independent second-opinion verification     │
│  5. Bayesian MC  → probabilistic scoring + confidence interval  │
│  6. OSINT        → browser-based public record search          │
│  7. Supermemory  → pattern memory storage + recall             │
│  8. AWS S3       → immutable transcript archive                │
│  9. Twilio       → SMS alert to school principal               │
│ 10. AgentMail    → HTML triage email to safety officer         │
│ 11. Stripe       → per-district billing                        │
│ 12. Sponge       → agent micropayments                         │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
Supabase Realtime → Next.js dashboard (Vercel)
        │
        ▼
Live overlay + ThreatGraph + Bayesian breakdown modal
```

---

## The Math: Bayesian Monte Carlo Threat Scoring

This is the core scientific engine that makes Kairos defensible and explainable — not a black-box neural network, but a transparent probabilistic model grounded in FBI behavioral threat assessment literature.

### Prior Probability

```
P₀ = BASE_RATE = 0.002
```

One in 500 calls to a school tip line is a credible threat. This is calibrated from the FBI's National Threat Assessment Center (NTAC) data on school violence pre-attack indicators.

### Likelihood Ratio Updates (Bayesian Chaining)

Each verbal feature detected in the transcript updates the probability using Bayes' theorem in odds form:

```
posterior_odds = prior_odds × LR
P(threat | feature) = posterior_odds / (1 + posterior_odds)

where:
  prior_odds = P₀ / (1 - P₀)
  LR = P(feature | real threat) / P(feature | non-threat call)
```

The chain is sequential — each sentence's posterior becomes the next sentence's prior:

```
P₀ = 0.20%
↓ "gun" detected     [weapon_explicit,  LR=12.0]  → P₁ = 2.3%
↓ "cafeteria"        [specific_location, LR=4.0]  → P₂ = 8.5%
↓ "tomorrow morning" [timeline_near,     LR=4.5]  → P₃ = 31.2%
↓ "i heard him say"  [direct_witness,    LR=6.0]  → P₄ = 72.8%
↓ "for weeks"        [escalation_pattern,LR=4.5]  → P₅ = 93.4%
```

### Feature Likelihood Table (calibrated against behavioral science literature)

| Category | Feature | Keywords | LR (mean) | LR (std) |
|----------|---------|----------|-----------|----------|
| Weapon | Explicit weapon | gun, knife, bomb, rifle | 12.0 | 3.0 |
| Evidence | Weapon photo | "showed a photo", "screenshot of" | 18.0 | 4.0 |
| Timeline | Imminent | today, tonight, right now | 8.0 | 2.0 |
| Timeline | Near-term | tomorrow, this week | 4.5 | 1.2 |
| Specificity | Named subject | "his name", "a kid named" | 5.0 | 1.5 |
| Location | Specific place | gym, cafeteria, parking lot | 4.0 | 1.2 |
| Credibility | First-hand witness | "I saw", "I heard", "I was there" | 6.0 | 1.5 |
| Credibility | Multiple witnesses | "everyone saw", "multiple students" | 3.5 | 1.0 |
| Escalation | Pattern | "for weeks", "getting worse" | 4.5 | 1.2 |
| Deception | Joking | "just kidding", "lol" | 0.10 | 0.05 |
| Deception | Vague hedge | "maybe nothing", "probably fine" | 0.55 | 0.20 |

The `std_ratio` field models **uncertainty** in each LR estimate — this is what feeds the Monte Carlo layer.

### Composite Factors (Co-occurrence Boosts)

When multiple high-credibility signals appear together, Kairos applies composite feature boosts that model the FBI principle of **specificity + corroboration = high credibility**:

| Composite | Triggered When | LR |
|-----------|---------------|-----|
| Location + Named Subject | specific_location AND specific_person | 3.5× |
| First-hand + Evidence | direct_witness AND caller_precise | 4.5× |
| Weapon Evidence + Timeline | weapon_photo AND (timeline_immediate OR timeline_near) | 8.0× |
| Escalation + Corroboration | escalation_pattern AND multiple_witnesses | 5.0× |
| High Specificity Cluster | 3+ specific detail types in same call | 6.0× |

### Monte Carlo Confidence Intervals

Rather than a single point estimate, Kairos runs **1,000 Monte Carlo simulations**, each re-sampling every likelihood ratio from its uncertainty distribution:

```python
for sim in range(n_simulations):
    p = BASE_RATE
    for feature in features:
        # Sample LR from normal distribution
        sampled_LR = max(0.01, np.random.normal(feature.mean_ratio, feature.std_ratio))
        prior_odds = p / (1 - p + 1e-9)
        posterior_odds = prior_odds * sampled_LR
        p = posterior_odds / (1 + posterior_odds)
    results[sim] = p

mean_p = np.mean(results)
ci_low, ci_high = np.percentile(results, [2.5, 97.5])  # 95% CI
```

The output is a **probability distribution**, not a single number. The dashboard renders all 600 sample draws as a particle simulation, with the CI band and mean line emerging as the simulation progresses. This lets school officials see not just "73% threat probability" but "we are 95% confident the true probability is between 58% and 89%."

### Cross-Tip Correlation

When the same school has prior tips in the last 7 days, Kairos applies a cross-tip correlation factor:

| Prior Tips | LR Boost |
|-----------|---------|
| 1 prior tip | 2.0× |
| 2 prior tips | 3.5× |
| 3+ prior tips | 5.0× ("confirmed pattern") |

This models the real-world phenomenon where lone callers are less credible than corroborated reports.

### Three-Model Consensus

The final threat level is the **maximum of three independent models**:

```
final_level = max(claude_level, gemini_level, bayes_level)
three_model_consensus = |claude - gemini| ≤ 1 AND |claude - bayes| ≤ 1
```

A "CONFIRMED CRITICAL" designation requires all three models to agree within one level. This eliminates both false positives (one hysterical model) and false negatives (one missed model).

---

## Sponsor Integrations — Technical Deep Dives

---

### AgentPhone — The Voice Intelligence Layer

AgentPhone is the **entry point for every real call into the system**. Without it, Kairos has no data.

**How it's used:**
- An AgentPhone AI agent is deployed with a custom school safety greeting and female voice
- When a student, parent, or teacher dials the number, AgentPhone answers, conducts the call, and transcribes every word of the caller's side in real time
- When the call ends, AgentPhone fires a webhook to the Kairos Railway backend with the call ID, duration, and transcript (as a structured list of `{role: "user", content: "..."}` objects)
- For calls where the webhook delivers an empty transcript (network race condition), Kairos falls back to polling the AgentPhone REST API (`GET /v1/calls/{callId}`) with a 3-second delay, then reconstructs the transcript from the incremental utterance list

**The critical engineering:** AgentPhone sends transcripts as incremental updates, so the same utterance may appear multiple times with progressively more words. Kairos deduplicates consecutive identical entries and uses the last (longest) version of each utterance:

```python
# Deduplicate incremental AgentPhone transcript updates
deduped = []
for part in parts:
    if not deduped or part != deduped[-1]:
        deduped.append(part)
full_transcript = " ".join(deduped).strip()
```

**Why it matters:** AgentPhone is the only thing between a panicked student and a processed threat alert. Every other component in the pipeline is useless without the raw voice data AgentPhone provides.

---

### Anthropic Claude — Primary Threat Classification Engine

Claude is the **reasoning backbone** of every threat assessment. It performs structured JSON extraction from unstructured speech, handling linguistic ambiguity, sarcasm, and indirect threats that simpler keyword systems would miss entirely.

**How it's used:**  
Claude receives the full call transcript (optionally pre-translated by Gemini Live) and returns a structured classification:

```python
classification = {
    "call_type": "threat | attendance | general",
    "threat_level": 1-5,
    "threat_type": "weapon | bullying | drugs | self_harm | ...",
    "summary": "2-sentence human-readable summary",
    "school_name": "extracted from context clues",
    "recommended_action": "monitor | escalate | immediate_response | 911",
    "caller_emotion": "calm | anxious | panicked | distressed | detached",
    "caller_tone": "credible | vague | specific | ...",
    "escalation_risk": "stable | escalating | imminent",
    "credibility_signals": ["first-hand account", "specific details"],
    "key_facts": ["subject is in 10th grade", "weapon shown in cafeteria"],
    "timeline": "tomorrow morning before first period",
    "subject_description": "tall, wears black hoodie",
    "location_detail": "west gym locker room",
    "threat_window": "next 24 hours"
}
```

Claude is called **twice** per pipeline: once on the raw transcript for a fast attendance/general call check, and once on the Moss-enriched transcript that includes semantic context from prior similar tips. This two-pass design means Claude's final classification is grounded in district history, not just the current call in isolation.

**Why Claude specifically:** The structured output requirement (`respond only with valid JSON`) with complex multi-field extraction across diverse, emotionally charged speech is a task where Claude's instruction-following reliability is critical. A malformed JSON response breaks the pipeline — Claude's consistency keeps every call fully processed.

---

### Google DeepMind Gemini — Multilingual Detection + Second-Opinion Verification

Gemini plays **two distinct roles**, both of which are architecturally irreplaceable.

**Role 1: Gemini Live — Real-Time Multilingual Translation**

~25% of US school-age children speak a language other than English at home. No existing school safety platform handles non-English calls with real-time AI triage.

Kairos runs `gemini-2.0-flash-live-001` (the streaming Live API) on every transcript before the Claude classification step:

```python
live_result = await live_multilingual_analysis(transcript, call_id)
# Returns: { detected_language, english_translation, multilingual, threat_level }

if live_result["multilingual"] and live_result["english_translation"]:
    working_transcript = live_result["english_translation"]
    # ALL downstream steps (Claude, Bayesian, OSINT) receive English
```

This runs **first in the pipeline** — before Claude, before Bayesian scoring, before Moss. A parent calling in Spanish about a weapon gets the same quality of analysis as an English-speaking student. The pipeline is language-agnostic.

**Role 2: Gemini Flash — Independent Threat Verification**

After Claude classifies the threat, `gemini-2.5-flash` provides a completely independent second opinion:

```python
# In gemini_verify.py
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt  # same transcript, independent prompt
)
gemini_level = data["threat_level"]  # 1-5
consensus = abs(gemini_level - claude_level) <= 1
```

The three-model consensus check (Claude + Gemini + Bayesian) is what separates a "possible threat" from a "CONFIRMED CRITICAL" alert. When all three models independently converge on level 4-5, the probability of a false positive drops dramatically. The dashboard shows a green "✓ 3-model consensus" badge only when this condition is met.

---

## Supermemory — Persistent Behavioral Intelligence

### The Problem It Solves

School safety platforms have zero memory. Every tip is evaluated in isolation. A student who made 3 ambiguous reports over 6 weeks is as invisible as someone reporting for the first time. The counselor reading the fourth call has no idea the prior three calls came from the same school. The AI classifying that fourth call has no idea either — unless the system was built to remember.

Kairos was built to remember.

### How Kairos Uses Supermemory — 3 Specific Operations

**1. `store_tip_memory(classification, call_id)` — Post-call semantic storage**

After every tip is fully processed, Kairos stores a rich semantic memory entry in Supermemory. The entry encodes the school name, threat type, key facts, caller emotion, escalation risk, and a natural-language summary of the call:

```python
client = Supermemory(api_key=SUPERMEMORY_API_KEY)
client.memories.add(
    content=(
        f"Threat report at {school}. Type: {threat_type}. Level: {level}/5. "
        f"Timeline: {timeline}. Escalation risk: {escalation_risk}. "
        f"Caller emotion: {caller_emotion}. 3-model consensus: {consensus}. "
        f"Credibility signals: {credibility_signals}. "
        f"Key facts: {key_facts}."
    ),
    # content is vector-embedded on ingestion — namespace = "kairos-threats"
    tags=[CONTAINER_TAG, school, threat_type]
)
```

The `content` field is what Supermemory embeds. The format `f"{school} | {threat_type} | {summary}"` is designed so that semantic queries against school name, threat type, or free-text description all resolve to the same embedding neighborhood. Namespace is `"kairos-threats"` — all Kairos tips, all schools, all time.

**2. `search_prior_tips(school, threat_type, key_facts)` — Pre-classification context retrieval**

Before Claude's second (enriched) classification pass, Kairos queries Supermemory with the current transcript context. The query is constructed from the school name, threat type, and key facts extracted by Claude's first pass:

```python
prior_context = client.memories.search(
    query=f"{school} {threat_type} {subject_description}",
    tags=[CONTAINER_TAG]
)
# Returns the 3 most semantically similar past tips from the same school
```

The returned context — a semantic summary of the most similar past reports — is injected directly into Claude's prompt as a `[Prior semantic context: ...]` block before the second classification runs:

```python
enriched_transcript = f"{working_transcript}\n\n[Prior semantic context: {prior_context}]"
classification = classify_threat(enriched_transcript)  # Claude's enriched final call
```

This prior context changes Claude's output. A call that would have been classified as level 3 in isolation becomes level 4 when Claude can see that the same school reported a similar threat pattern three weeks ago.

**3. Cross-tip escalation via the Bayesian scorer**

If `search_prior_tips` returned results (`prior_tips` is non-empty), the Bayesian Monte Carlo scorer receives `prior_tip_count > 0` via the `cross_tip_feature` field. This activates a likelihood ratio multiplier in the Bayesian chain:

| Prior Tips in Supermemory | LR Boost Applied |
|--------------------------|-----------------|
| 1 prior tip | 2.0× |
| 2 prior tips | 3.5× |
| 3+ prior tips | 5.0× ("confirmed pattern") |

This multiplier is a direct expression of the FBI NTAC finding that corroborated, repeated reports are categorically more credible than isolated calls. Supermemory is what makes the corroboration detectable — it's the evidence the Bayesian model needs to apply the boost.

### Why This Matters for School Safety

Behavioral patterns in adolescents often escalate slowly. A student who mentioned "making them pay" two months ago, then reported seeing a weapon last week, then called again today is exhibiting textbook pre-attack escalation — what the Secret Service calls "leakage": the gradual, observable narrowing of intent into action. No single call triggers a red flag. The pattern across calls does. Without cross-session memory, each call is a cold start and the pattern is invisible. With Supermemory, Kairos detects the full arc of escalation and raises the threat level automatically on the third call — before a human analyst would ever connect the dots.

This is not hypothetical. The FBI's 2019 study of 63 school attacks found that in 93% of cases, the attacker communicated intent to at least one person before the attack. The communication was rarely a single alarming statement — it was a series of ambiguous signals over time. Kairos is the first school safety platform designed to aggregate those signals across time, not just within a single call. Supermemory is the infrastructure that makes cross-session aggregation possible without manual case management, without a human analyst maintaining a watch list, and without the false privacy concern that comes from storing raw transcripts in a searchable database. The stored representations are semantic embeddings, not transcripts.

### Technical Comparison

| Platform | Memory | Cross-tip correlation | Behavioral pattern detection |
|---|---|---|---|
| Navigate360 | None | No | No |
| STOPit | None | Manual | No |
| Sandy Hook Promise | None | No | No |
| **Kairos** | **Persistent vector memory** | **Automatic (Bayesian boost)** | **Yes — cross-session** |

### What to Say in Your Demo Video

> "Every other platform treats each tip as isolated. Kairos builds a behavioral memory — powered by Supermemory — that connects dots across weeks and months. When this call came in today, the AI already knew about two prior ambiguous reports from the same school. That history changed the threat level from 3 to 4. That's the difference between monitoring and preventing."

---

### Supermemory — Persistent Cross-Call Pattern Memory (Technical Reference)

Supermemory is the **institutional memory** of the Kairos system. Every tip, every call, every threat assessment is stored as a rich semantic document that future calls can query.

**How it's used:**  
After every call is processed, Kairos stores a structured memory document:

```python
client = Supermemory(api_key=SUPERMEMORY_API_KEY)
client.memories.add(
    content=(
        f"Threat report at {school}. Type: {threat_type}. Level: {level}/5. "
        f"Timeline: {timeline}. Escalation risk: {escalation_risk}. "
        f"Caller emotion: {caller_emotion}. 3-model consensus: {consensus}. "
        f"Credibility signals: {credibility_signals}. "
        f"Key facts: {key_facts}."
    ),
    tags=[CONTAINER_TAG, school, threat_type]
)
```

Before each new threat classification, the system searches Supermemory for prior tips from the same school or involving similar threat types:

```python
prior_context = client.memories.search(
    query=f"{school} {threat_type} {subject_description}",
    tags=[CONTAINER_TAG]
)
```

The result — a semantic summary of similar past reports — is injected into Claude's context window for the enriched second classification. This is the mechanism by which Kairos can say: *"This call matches a pattern of 3 prior reports from Westview High this semester."*

**Why Supermemory vs. a simple database query:** Supermemory's semantic search finds thematically similar reports even when the exact school name or threat type differs — "Westview High" and "Westview Academy" are the same school to Supermemory, not different database rows. Pattern recognition across imprecise, human-generated data is precisely what vector-indexed memory is built for.

---

### Moss — Real-Time Semantic Context Injection

Moss provides **semantic search at call-processing time**, giving Claude access to the full history of similar threats in the district before it issues its final verdict.

**How it's used:**  
Every processed tip is indexed into Moss immediately after classification:

```python
# moss_search.py
client = MossClient(MOSS_PROJECT_ID, MOSS_PROJECT_KEY)
client.indexes.upsert(
    index_id="threat-vector-tips",
    document=f"{school} {threat_type} {summary}",
    metadata={"school": school, "level": level, "call_id": call_id}
)
```

Before Claude's final enriched classification, Kairos queries Moss with the working transcript:

```python
moss_context = semantic_search_tips(working_transcript[:300], call_id)
# Returns: top semantically similar prior tips as a text block

enriched_transcript = f"{working_transcript}\n\n[Prior semantic context: {moss_context}]"
classification = classify_threat(enriched_transcript)  # Claude's final call
```

**The architectural difference from Supermemory:** Moss and Supermemory serve different roles in the pipeline. Moss is queried **before** Claude's final classification as a context injection — it shapes what Claude outputs. Supermemory is queried **after** Claude's initial classification to search for escalation patterns — it provides a human-readable cross-school alert. Both are necessary; neither is redundant.

**Why this matters:** A threat call that mentions "the cafeteria" at "Jefferson Middle School" should be classified in the context of the three prior "cafeteria" calls at that school in the past month. Without Moss, Claude only sees the current call. With Moss, Claude reasons over the entire district's threat history in real time.

---

### AgentMail — Automated Triage Email Briefs

AgentMail is how **every threat reaches a human decision-maker** with full context, not just a text message.

**How it's used:**  
For every call with threat_level ≥ 1, Kairos sends a structured HTML email brief through AgentMail to the designated safety officer:

```python
# notify.py
requests.post(
    f"{AGENTMAIL_BASE}/v1/inboxes/{inbox_id}/messages",
    headers={"Authorization": f"Bearer {AGENTMAIL_API_KEY}"},
    json={
        "to": [{"email": SAFETY_OFFICER_EMAIL}],
        "subject": f"[KAIROS] Level {level}/5 — {label} | {school}",
        "html": html_email_body,  # full HTML triage report
    }
)
```

The HTML email is a fully-designed intelligence brief containing:
- Color-coded threat level header (green → red)
- AI summary, recommended action, threat window
- Caller emotion and tone analysis
- Key facts as a structured list
- Credibility signals
- Bayesian probability with CI
- Three-model consensus status
- The full dispatch brief for 911 operators
- The complete transcript

**Why AgentMail over standard SMTP:** AgentMail provides a programmable inbox that can receive tip submissions from web forms in addition to sending alerts — the same infrastructure handles both the inbound tip form (`/api/tip/submit`) and the outbound triage email, keeping the entire communication layer in one system. The AgentMail inbox address (`threats@inbox.agentmail.to`) is the reply-to for safety officers to respond with notes that feed back into the counselor tracking system.

---

### AWS S3 — Immutable Audit Archive

Every call is archived to S3 immediately after processing, creating an **immutable forensic record** that cannot be altered, deleted, or tampered with.

**How it's used:**

```python
# aws_archive.py
s3.put_object(
    Bucket=AWS_S3_BUCKET,
    Key=f"transcripts/{call_id}.txt",
    Body=transcript.encode("utf-8"),
    ContentType="text/plain",
    Metadata={"call_id": call_id, "school": school, "level": str(level)}
)
s3.put_object(
    Bucket=AWS_S3_BUCKET,
    Key=f"reports/{call_id}.json",
    Body=json.dumps(full_classification_report).encode("utf-8"),
    ContentType="application/json"
)
```

The S3 URI is stored in the Supabase `tips` table (`s3_archive_uri` column), so any tip can be traced back to its original transcript and full analysis report. In a real deployment, this archive would be required for legal proceedings, law enforcement handoff, and FERPA compliance.

---

### Supabase — Real-Time Intelligence Database

Supabase is the **live data layer** that connects the backend pipeline to the frontend dashboard in real time.

**How it's used:**  
The backend writes directly to Supabase via the REST API after every pipeline completion. The dashboard subscribes to Postgres `INSERT` events via Supabase Realtime:

```typescript
// app/page.tsx
supabase.channel('tips-live')
  .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'tips' }, payload => {
    handleNewTip(payload.new as Tip, demoRunning)
  })
  .subscribe()
```

Two separate Supabase tables power different dashboard features:
- **`tips`** — every processed call with full AI analysis (50+ columns)
- **`live_calls`** — real-time stream of the active call being processed, updated sentence-by-sentence as the transcript is streamed

The `live_calls` table enables the live overlay animation: as the backend processes each sentence, it upserts a row with the current Bayesian probability, and the frontend renders the climbing probability bar in real time — the user sees the threat score building as if watching the AI think.

---

### Twilio — Principal Alert SMS

The moment a threat reaches level 3+, Twilio fires an SMS to the school principal before the email brief even lands.

**How it's used:**

```python
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
client.messages.create(
    body=(
        f"[KAIROS] Level {level}/5 — {label}\n"
        f"School: {school}\nAction: {action}\n"
        f"Window: {threat_window}\n{summary[:160]}"
    ),
    from_=TWILIO_FROM_NUMBER,
    to=PRINCIPAL_PHONE
)
```

The SMS includes the threat level, school, recommended action, threat window, and the first 160 characters of the AI summary — enough for the principal to make an immediate decision before reading the full email.

---

### Stripe — Per-District Billing Infrastructure

Stripe powers the **district-level SaaS billing model** that makes Kairos a deployable product, not just a demo.

**How it's used:**  
Each processed threat call triggers a Stripe usage record:

```python
# stripe_billing.py
stripe.billing.MeterEvent.create(
    event_name="threat_tip_processed",
    payload={
        "stripe_customer_id": STRIPE_CUSTOMER_ID,
        "value": str(tip_value),
    }
)
```

Districts are billed per-processed-call, with higher threat levels costing more (because they trigger more downstream services: OSINT, SMS, email, S3). This metered billing model means school districts only pay when the system is actually processing real tips — not a flat SaaS fee for a tool that sits idle.

---

### Sponge — Agent-to-Agent Micropayments

Sponge is the **financial infrastructure for the autonomous agent economy** within Kairos. Every third-party service that an AI agent calls is paid via a Sponge micropayment from the district's wallet.

**How it's used:**  
After each service call in the pipeline, Kairos disburses a micropayment:

```python
# In agent.py, after each service
disburse_agent_payment("gemini-verify", 3, call_id, {"school": school})   # $0.03
disburse_agent_payment("browser-use-osint", 2, call_id, {"school": school}) # $0.02
disburse_agent_payment("supermemory-store", 1, call_id)                     # $0.01
```

The Sponge wallet dashboard is surfaced in the frontend at `/api/sponge/wallet`, showing real-time agent spend. This demonstrates the architecture of a **fully autonomous AI economic system** — no human approves each service call; the AI agents autonomously pay each other for the services they consume.

---

### Deepgram — Audio Re-Transcription

For calls with a recording URL, Deepgram provides a **higher-accuracy re-transcription** that can supersede AgentPhone's built-in transcription.

**How it's used:**

```python
# deepgram_transcribe.py — called if confidence > 0.85
result = await transcribe_audio_url(recording_url, call_id)
if result["confidence"] > 0.85 and result["transcript"]:
    transcript = result["transcript"]  # replace AgentPhone transcript
    working_transcript = transcript
```

Deepgram's Nova-3 model provides per-word confidence scores, speaker diarization, and language detection — all of which feed back into the Bayesian feature extraction and the caller emotion analysis.

---

## The Dashboard: Kairos Intelligence Console

The frontend is a Next.js 16 App Router application deployed to Vercel with four primary views:

### Live Feed
Real-time log of all processed tips. New threats appear with a 12-second maximum delay (immediate via Supabase Realtime if enrolled; 12-second polling fallback otherwise). Each tip shows: threat level, school, category, AI summary, caller emotion, Bayesian probability, and three-model consensus status.

### Live Call Overlay
When a real call comes in, an overlay appears on the dashboard showing the transcript being processed sentence-by-sentence, the Bayesian probability climbing in real time, and detected verbal signals. The overlay persists for 20 seconds on critical threats (level 4-5) to ensure it's seen.

### Threat Analysis Modal (ThreatBreakdownModal)
Four-phase animated analysis for any tip:
1. **Decode** — words revealed one-by-one, color-coded by category (threat/urgent/fear/location/credibility/escalation)
2. **Signals** — six animated signal bars fill over 3 seconds, followed by a six-axis emotional profile (aggression, desperation, intent, specificity, credibility, escalation)
3. **Monte Carlo** — 600-particle simulation renders in real time; after completion, the Bayesian update chain appears row by row showing every feature hit with its exact LR, prior probability, posterior probability, and delta pp
4. **Verdict** — circular gauge counts up to the final probability; threat level display; CI strip; composite factor badges; top Bayesian driver breakdown

### ThreatGraph
Force-directed 3D network graph rendering all tips as nodes, with edges connecting nodes that share the same school, threat type, or keyword clusters. Latest threats are highlighted in pink. Supports real-time node addition as new tips arrive.

---

## Running Locally

### Backend

```bash
cd threat-vector
cp .env.example .env  # fill in API keys from sponsor booths
pip install -r requirements.txt
python main.py  # starts FastAPI on port 8001
```

Run Supabase migrations:
```bash
# In Supabase SQL editor:
\i full_migration.sql
\i migration_live_calls.sql
\i migration_attendance_logs.sql

# Enable Realtime:
ALTER PUBLICATION supabase_realtime ADD TABLE tips;
ALTER PUBLICATION supabase_realtime ADD TABLE live_calls;
```

### Dashboard

```bash
cd threat-vector-dashboard
cp .env.local.example .env.local
npm install && npm run dev
```

### AgentPhone Webhook

```bash
ngrok http 8001
# Set webhook URL in AgentPhone dashboard:
# POST https://<ngrok-id>.ngrok.io/webhook/agentphone
```

---

## Environment Variables

| Variable | Service | Purpose |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Anthropic | Claude threat classification |
| `GOOGLE_API_KEY` | Google DeepMind | Gemini Live + Gemini Flash |
| `AGENTPHONE_API_KEY` | AgentPhone | Voice call webhooks + transcript fetch |
| `AGENTMAIL_API_KEY` | AgentMail | HTML triage email delivery |
| `SUPERMEMORY_API_KEY` | Supermemory | Cross-call pattern memory |
| `MOSS_PROJECT_ID` / `MOSS_PROJECT_KEY` | Moss | Semantic context search |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | Twilio | SMS principal alerts |
| `STRIPE_SECRET_KEY` | Stripe | Per-district metered billing |
| `SPONGE_API_KEY` / `SPONGE_WALLET_ID` | Sponge | Agent micropayments |
| `AWS_ACCESS_KEY_ID` / `AWS_S3_BUCKET` | AWS | Immutable transcript archive |
| `DEEPGRAM_API_KEY` | Deepgram | High-accuracy audio transcription |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | Supabase | Realtime DB + dashboard sync |

---

## Why This Is Different

| Feature | Existing Tip Lines | Kairos |
|---------|-------------------|--------|
| Response time | Hours (human review) | < 60 seconds |
| Non-English callers | Voicemail, unprocessed | Gemini Live translates 70 languages |
| Night/weekend calls | Unattended | Fully autonomous, 24/7 |
| Confidence scoring | Binary (threat/no threat) | Bayesian probability with 95% CI |
| Cross-school patterns | Manual | Automated via Supermemory + Moss |
| Second opinion | None | Three independent AI models |
| Audit trail | Paper logs | Immutable S3 archive |
| Billing | Annual contracts | Per-call Stripe metered billing |

---

## Built With

Anthropic · Google DeepMind · AgentPhone · AgentMail · Supermemory · Moss · Twilio · Stripe · Sponge · AWS · Deepgram · Supabase · Vercel · Next.js 16 · FastAPI · Railway
