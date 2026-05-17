# Threat Vector — Codex Task Queue

## Project Context

Threat Vector is a voice-first anonymous school threat reporting system built for the YC "Call My Agent" Hackathon.

**Architecture:**
- Backend: FastAPI (Python), `/Users/ishaansamantray/Desktop/threat-vector/`, port 8001
- Frontend: Next.js 16 + Tailwind v4 + Three.js, `/Users/ishaansamantray/Desktop/threat-vector-dashboard/`, port 3002
- Database: Supabase (Postgres + Realtime)
- GitHub: `devteamaegis/threat-vector` and `devteamaegis/threat-vector-dashboard`
- Live URL: https://caden-bigger-picture.vercel.app

**Call pipeline (in order):**
Gemini Live (multilingual) → Moss (semantic search) → Claude (classify) → Gemini Flash (second opinion) → Supabase (log) → AWS S3 (archive) → Supermemory (memory) → AgentMail (email) → Twilio (SMS) → Stripe (bill) → Sponge (micropayments)

All integrations gracefully skip with a WARNING log when keys are missing (`.env` has `FILL_IN` placeholders).

---

## Task 1 — Fix requirements.txt

**File:** `/Users/ishaansamantray/Desktop/threat-vector/requirements.txt`

**Problem:** Missing dependencies that are now imported in the codebase.

**Replace the entire file with:**
```
fastapi
uvicorn[standard]
anthropic>=0.100.0
twilio>=9.0.0
requests>=2.31.0
python-dotenv>=1.0.0
httpx>=0.27.0
stripe>=9.0.0
supermemory>=3.0.0
google-genai>=1.0.0
boto3>=1.34.0
langchain-openai>=0.1.0
browser-use>=0.12.0
```

**Also create** `/Users/ishaansamantray/Desktop/threat-vector/Procfile` with:
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## Task 2 — Add Langfuse observability to classifier.py

**File:** `/Users/ishaansamantray/Desktop/threat-vector/classifier.py`

**What:** Every Claude classification call should be logged to Langfuse (LLM observability). If `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are not set, skip silently.

**How:**
1. Add `langfuse` to requirements.txt
2. At the top of `classifier.py`, add optional Langfuse init:

```python
import os, time

def _get_langfuse():
    try:
        from langfuse import Langfuse
        pk = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        sk = os.getenv("LANGFUSE_SECRET_KEY", "")
        if not pk or not sk or pk == "FILL_IN":
            return None
        return Langfuse(public_key=pk, secret_key=sk)
    except ImportError:
        return None
```

3. In `classify_threat()`, wrap the API call:

```python
def classify_threat(transcript: str) -> dict:
    lf = _get_langfuse()
    trace = lf.trace(name="threat-classification") if lf else None
    span = trace.span(name="claude-classify") if trace else None

    t0 = time.time()
    prompt = CLASSIFICATION_PROMPT.format(transcript=transcript)
    message = _get_client().messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    latency_ms = int((time.time() - t0) * 1000)

    text = message.content[0].text.strip()
    result = {}
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        result = json.loads(match.group()) if match else {}

    if span:
        span.end(
            output=result,
            metadata={
                "latency_ms": latency_ms,
                "threat_level": result.get("threat_level"),
                "model": "claude-opus-4-5",
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            }
        )
    return result
```

4. Add to `.env` (append, don't overwrite):
```
LANGFUSE_PUBLIC_KEY=FILL_IN
LANGFUSE_SECRET_KEY=FILL_IN
LANGFUSE_HOST=https://cloud.langfuse.com
```

---

## Task 3 — Dashboard: Fix 7 UI layout issues

**File:** `/Users/ishaansamantray/Desktop/threat-vector-dashboard/app/page.tsx`

Fix all 7 of these in a single edit pass:

### 3a — "ANALYZING" text appears twice
In the left panel, there's a STATUS section showing "ANALYZING" and the orb area also shows "ANALYZING". Find the duplicate and remove the one in the left stats panel. The orb section should be the only place showing the current mode text.

### 3b — Left panel stat gaps
The left panel has 4 `<Stat>` components with `justify-between` but large empty space between them. Change the stats container from `justify-between` to `gap-6 flex-wrap` so stats sit close together.

### 3c — Orb off-center
The orb container has inconsistent padding causing it to appear ~38% from the left instead of centered. Find the orb wrapper div and ensure it uses `flex items-center justify-center w-full`.

### 3d — Emoji filter chips
The feed filter chips use emoji (🔴 🟠 etc). Replace them with clean text-only pills:
- `all` → "All"
- `critical` → "Critical" (with red dot indicator `•`)
- `high` → "High" (orange dot)
- `weapon` → "Weapon"

Use this pattern:
```tsx
<button className={`px-3 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wide transition-colors ${
  filter === f ? 'bg-white/10 text-white' : 'text-slate-600 hover:text-slate-400'
}`}>
```

### 3e — Bottom half dead space
The bottom half of the dashboard below the tip feed is empty. Add a compact **Integration Status Grid** showing all 9 integrations as colored dots (green = key set, grey = missing):

```tsx
function IntegrationStatus() {
  const integrations = [
    { name: 'Anthropic', key: 'configured' },
    { name: 'AgentPhone', key: 'configured' },
    { name: 'AgentMail', key: 'pending' },
    { name: 'Supermemory', key: 'pending' },
    { name: 'Moss', key: 'pending' },
    { name: 'Stripe', key: 'pending' },
    { name: 'Sponge', key: 'pending' },
    { name: 'AWS S3', key: 'pending' },
    { name: 'Gemini', key: 'pending' },
  ]
  // fetch from /api/integrations or use static for now
}
```

Actually: fetch `${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8001'}/health` on mount, and display real status for each integration as a row of small indicators at the bottom of the left panel.

### 3f — "N" artifact at bottom-left
There's a stray `N` character appearing at the bottom-left during initial load. This is likely from a hydration mismatch or a leftover `<span>` or text node. Search for any standalone `N` or `{'\n'}` in JSX and remove it.

### 3g — Sponsor ticker text too small
The sponsor ticker at the bottom has text at ~8-9px, illegible. Increase to `text-[11px]` and add `font-medium`. Also increase the ticker item padding from `px-4` to `px-6`.

---

## Task 4 — Dashboard: Add multilingual call indicators

**File:** `/Users/ishaansamantray/Desktop/threat-vector-dashboard/app/page.tsx`
**File:** `/Users/ishaansamantray/Desktop/threat-vector-dashboard/lib/supabase.ts`

**Context:** The Gemini Live API detects the caller's language. Non-English calls are translated before Claude processes them. The `caller_language` and `multilingual_call` fields are stored in Supabase.

**Step 1 — Update Tip type in supabase.ts:**
Add these fields:
```typescript
caller_language?: string | null
multilingual_call?: boolean | null
english_translation?: string | null
gemini_level?: number | null
gemini_reasoning?: string | null
consensus?: boolean | null
s3_archive_uri?: string | null
```

**Step 2 — TipRow component:** When `tip.multilingual_call === true`, show a language badge next to the school name:
```tsx
{tip.multilingual_call && tip.caller_language && (
  <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-950/60 border border-indigo-800/30 text-indigo-400">
    🌐 {tip.caller_language}
  </span>
)}
```

**Step 3 — TipDrawer component:** Add a "Multi-Model Consensus" section between "AI Assessment" and "Caller Analysis":
```tsx
{(tip.gemini_level != null || tip.consensus != null) && (
  <div className="rounded-lg p-4" style={{ background: 'rgba(16,185,129,0.04)', border: '1px solid rgba(16,185,129,0.12)' }}>
    <div className="text-[9px] font-bold uppercase tracking-[0.2em] text-emerald-700 mb-3">Multi-Model Consensus</div>
    <div className="grid grid-cols-3 gap-3 text-xs">
      <div>
        <div className="text-slate-700 mb-0.5 text-[9px]">Claude</div>
        <div className="text-orange-400 font-bold">{tip.ai_triage_score ?? '–'}/10</div>
      </div>
      <div>
        <div className="text-slate-700 mb-0.5 text-[9px]">Gemini</div>
        <div className="text-blue-400 font-bold">{tip.gemini_level != null ? `${tip.gemini_level}/5` : '–'}</div>
      </div>
      <div>
        <div className="text-slate-700 mb-0.5 text-[9px]">Consensus</div>
        <div className={`font-bold ${tip.consensus ? 'text-green-400' : 'text-yellow-500'}`}>
          {tip.consensus ? 'CONFIRMED' : 'DIVERGENT'}
        </div>
      </div>
    </div>
    {tip.gemini_reasoning && (
      <p className="text-[10px] text-slate-600 mt-2 italic">{tip.gemini_reasoning}</p>
    )}
    {tip.multilingual_call && tip.caller_language && (
      <div className="mt-2 pt-2 border-t text-[10px] text-indigo-500" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
        🌐 Originally in {tip.caller_language} — auto-translated by Gemini Live
      </div>
    )}
  </div>
)}
```

**Step 4 — Demo tip:** Update `buildDemoTip()` to include:
```typescript
caller_language: 'English',
multilingual_call: false,
gemini_level: 5,
gemini_reasoning: 'Weapon photo evidence and escalating pattern strongly indicate imminent threat',
consensus: true,
```

---

## Task 5 — Dashboard: Update pipeline visualizer with all 10 integrations

**File:** `/Users/ishaansamantray/Desktop/threat-vector-dashboard/app/page.tsx`

Replace the `PIPELINE_STEPS` constant with the full 10-step pipeline:

```typescript
const PIPELINE_STEPS = [
  { id: 'gemini_live', label: 'Gemini Live', icon: '🌐', desc: 'Multilingual detect',  ms: 280  },
  { id: 'moss',        label: 'Moss',        icon: '🔍', desc: 'Semantic context',     ms: 620  },
  { id: 'claude',      label: 'Claude',      icon: '🧠', desc: 'Threat classify',      ms: 2400 },
  { id: 'gemini',      label: 'Gemini',      icon: '✦',  desc: 'Consensus verify',     ms: 3100 },
  { id: 'supabase',    label: 'Supabase',    icon: '🗄️', desc: 'Log to dashboard',     ms: 3400 },
  { id: 'aws',         label: 'AWS S3',      icon: '☁️', desc: 'Archive transcript',   ms: 3700 },
  { id: 'memory',      label: 'Memory',      icon: '🧬', desc: 'Pattern storage',      ms: 4100 },
  { id: 'twilio',      label: 'Twilio',      icon: '📱', desc: 'SMS to principal',     ms: 4600 },
  { id: 'agentmail',   label: 'AgentMail',   icon: '✉️', desc: 'Email brief',          ms: 5200 },
  { id: 'stripe',      label: 'Stripe',      icon: '💳', desc: 'Bill district',        ms: 5800 },
]
```

Also update `SPONSORS` constant to include Google DeepMind and AWS:
```typescript
const SPONSORS = [
  { name: 'Anthropic',      role: 'Claude AI',          color: '#f97316' },
  { name: 'Google DeepMind',role: 'Gemini Live',         color: '#4285f4' },
  { name: 'AgentPhone',     role: 'Voice Calls',         color: '#06b6d4' },
  { name: 'AgentMail',      role: 'Email Briefs',        color: '#8b5cf6' },
  { name: 'Supermemory',    role: 'Pattern Memory',      color: '#f59e0b' },
  { name: 'Moss',           role: 'Semantic Search',     color: '#6366f1' },
  { name: 'Stripe',         role: 'District Billing',    color: '#ec4899' },
  { name: 'Sponge',         role: 'Micropayments',       color: '#14b8a6' },
  { name: 'AWS',            role: 'Call Archive',        color: '#ff9900' },
  { name: 'Supabase',       role: 'Realtime DB',         color: '#10b981' },
]
```

---

## Task 6 — Dashboard: Add Stripe pricing modal

**File:** `/Users/ishaansamantray/Desktop/threat-vector-dashboard/app/page.tsx`

Add a `PricingModal` component and a "View Pricing" button in the left panel header area. This shows the business model to judges.

```tsx
function PricingModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <div className="relative z-10 rounded-2xl p-8 w-full max-w-sm"
        style={{ background: 'rgba(8,9,14,0.99)', border: '1px solid rgba(255,255,255,0.08)' }}
        onClick={e => e.stopPropagation()}>
        <div className="text-[9px] font-bold uppercase tracking-[0.3em] text-slate-600 mb-6">District Pricing</div>
        <div className="flex flex-col gap-3">
          {[
            { tier: 'Starter',    price: '$199/mo',  schools: '1–5 schools',   tips: '500 tips/mo' },
            { tier: 'District',   price: '$499/mo',  schools: '6–20 schools',  tips: 'Unlimited tips', highlight: true },
            { tier: 'State',      price: 'Custom',   schools: '20+ schools',   tips: 'White-label + API' },
          ].map(p => (
            <div key={p.tier} className={`rounded-lg p-4 ${p.highlight ? 'border border-cyan-500/30 bg-cyan-950/20' : 'border border-slate-800'}`}>
              <div className="flex items-center justify-between mb-1">
                <span className={`text-sm font-bold ${p.highlight ? 'text-cyan-400' : 'text-slate-300'}`}>{p.tier}</span>
                <span className={`text-sm font-black tabular-nums ${p.highlight ? 'text-white' : 'text-slate-400'}`}>{p.price}</span>
              </div>
              <div className="text-[10px] text-slate-600">{p.schools} · {p.tips}</div>
            </div>
          ))}
        </div>
        <div className="mt-4 text-[9px] text-slate-700 text-center">Powered by Stripe · Per-tip billing available</div>
        <button onClick={onClose} className="mt-4 w-full py-2 rounded-lg text-[11px] font-semibold text-slate-400 hover:text-white border border-slate-800 hover:border-slate-600 transition-colors">
          Close
        </button>
      </div>
    </div>
  )
}
```

Add `const [showPricing, setShowPricing] = useState(false)` to the Dashboard state, render `<PricingModal>` when true, and add a small "Pricing" button near the top of the left panel.

---

## Task 7 — Backend: Add `/api/integrations` route to dashboard

**File:** `/Users/ishaansamantray/Desktop/threat-vector-dashboard/app/api/integrations/route.ts`

Create a new route that proxies the backend `/health` endpoint and returns integration statuses to the dashboard. This lets the `IntegrationStatus` component (Task 3e) show real live status.

```typescript
import { NextResponse } from 'next/server'

export async function GET() {
  const backendUrl = process.env.BACKEND_URL || 'http://localhost:8001'
  try {
    const r = await fetch(`${backendUrl}/health`, { next: { revalidate: 30 } })
    if (!r.ok) throw new Error('backend unreachable')
    const data = await r.json()
    return NextResponse.json(data)
  } catch {
    // Return all-false when backend is unreachable (Vercel production)
    return NextResponse.json({
      status: 'backend_offline',
      integrations: {
        anthropic: false, supabase: true, twilio: false,
        agentphone: false, agentmail: false, supermemory: false,
        moss: false, stripe: false, sponge: false,
      }
    })
  }
}
```

Add `BACKEND_URL=http://localhost:8001` to `.env.local` and to Vercel env vars.

---

## Task 8 — Backend: Add Deepgram transcription quality display

**File:** `/Users/ishaansamantray/Desktop/threat-vector/deepgram_transcribe.py` (new file)

Deepgram provides higher-quality transcription than standard speech-to-text. For Threat Vector, use Deepgram to re-transcribe call recordings when available, and add a confidence score to the Supabase tip record.

```python
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
                "language": "multi",          # auto-detect language
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
```

Add `DEEPGRAM_API_KEY=FILL_IN` to `.env`.

Wire into `agent.py`: after extracting the transcript, if the AgentPhone webhook provides an audio URL (`body.get("recording_url")`), call `transcribe_audio_url()` and use the Deepgram transcript if confidence > 0.85.

---

## Task 9 — Dashboard: Add cost-per-tip tracker

**File:** `/Users/ishaansamantray/Desktop/threat-vector-dashboard/app/page.tsx`

Add a `CostTracker` component to the bottom of the left panel that shows the per-tip AI cost breakdown. Use static demo values (Sponge wallet balance not available until booth key is set).

```tsx
function CostTracker() {
  const costs = [
    { label: 'Gemini Live',  cost: 0.0008, color: 'text-blue-500' },
    { label: 'Claude',       cost: 0.0210, color: 'text-orange-500' },
    { label: 'Gemini Flash', cost: 0.0003, color: 'text-blue-400' },
    { label: 'AgentMail',    cost: 0.0010, color: 'text-purple-500' },
    { label: 'SMS (Twilio)', cost: 0.0075, color: 'text-red-500' },
    { label: 'AWS S3',       cost: 0.0001, color: 'text-yellow-600' },
  ]
  const total = costs.reduce((s, c) => s + c.cost, 0)
  return (
    <div className="rounded-lg p-3" style={{ background: 'rgba(255,255,255,0.015)', border: '1px solid rgba(255,255,255,0.04)' }}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[9px] font-bold uppercase tracking-[0.2em] text-slate-600">Cost Per Tip</span>
        <span className="text-[11px] font-black text-green-400 tabular-nums">${total.toFixed(4)}</span>
      </div>
      <div className="flex flex-col gap-1">
        {costs.map(c => (
          <div key={c.label} className="flex items-center justify-between">
            <span className={`text-[9px] ${c.color}`}>{c.label}</span>
            <span className="text-[9px] font-mono text-slate-600">${c.cost.toFixed(4)}</span>
          </div>
        ))}
      </div>
      <div className="mt-2 pt-2 border-t text-[9px] text-slate-700" style={{ borderColor: 'rgba(255,255,255,0.04)' }}>
        District billed $0.15–0.35 per tip via Stripe · Sponge handles agent micropayments
      </div>
    </div>
  )
}
```

Place this component at the bottom of the left panel, above the sponsor ticker.

---

## Commit & Push Instructions

After completing each task, commit and push:

```bash
# Dashboard tasks (3-6, 9)
cd /Users/ishaansamantray/Desktop/threat-vector-dashboard
git add -A
git commit -m "feat: [task description]"
git push
# Vercel auto-deploys on push to main

# Backend tasks (1, 2, 7, 8)
cd /Users/ishaansamantray/Desktop/threat-vector
git add -A
git commit -m "feat: [task description]"
git push
```

## Environment Variables Summary

All `FILL_IN` values in `.env` need to be obtained at hackathon booths:

| Variable | Obtained from |
|----------|--------------|
| `AGENTPHONE_API_KEY` | AgentPhone booth |
| `AGENTPHONE_AGENT_ID` | AgentPhone dashboard |
| `AGENTMAIL_API_KEY` | AgentMail booth |
| `AGENTMAIL_INBOX_ID` | AgentMail dashboard |
| `GOOGLE_API_KEY` | Google DeepMind booth |
| `SUPERMEMORY_API_KEY` | Supermemory booth |
| `MOSS_API_KEY` | Moss booth (also update `MOSS_BASE` in `moss_search.py`) |
| `SPONGE_API_KEY` | Sponge booth (also update `SPONGE_BASE` in `sponge_payments.py`) |
| `STRIPE_SECRET_KEY` | Stripe booth |
| `TWILIO_ACCOUNT_SID` | Twilio booth |
| `AWS_ACCESS_KEY_ID` | AWS booth |
| `DEEPGRAM_API_KEY` | Deepgram booth |
| `LANGFUSE_PUBLIC_KEY` | Langfuse booth |
| `OPENAI_API_KEY` | OpenAI booth (YC credits) |
| `NGROK_URL` | Run `./start_with_ngrok.sh` — auto-sets this |
