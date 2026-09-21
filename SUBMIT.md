# SUBMIT.md — ArcLens (Cerebro PS-01)

**Track:** Tone intelligence · ₹5,000 · online  
**Event window:** Prefer IEM Nov 2–4 2026 if that schedule is authoritative; Unstop listing is LIVE.  
**Repo:** https://github.com/ankukumarsingh82-boop/cerebro-arclens  
**Team:** Anku Kumar (`ankukumarsingh82`)

## One-liner

ArcLens reads a chat export, tags every turn with tone + sarcasm cues, draws the emotion arc, and fires escalation alerts when the slope goes hostile.

## Problem

Support, ops, and group chats do not fail on a single swear word. They fail on a **curve**: mock-polite sarcasm, then a cliff, then rupture language. Existing sentiment widgets flatten that into a thumbs-down.

## What to demo (3 minutes)

1. `./run.sh` → http://127.0.0.1:8000
2. Click **Run incident demo** (`data/slack_incident.txt`), or open http://127.0.0.1:8000/?demo=1
3. Show the arc falling through the deploy, the sarcasm cluster (“Oh great. Just what we needed”), and the critical rupture (PII / chargebacks / “I am done covering”)
4. Switch to `whatsapp_dinner.txt` (personal WhatsApp format) and `json_standup.json` (warm control — should not go critical)
5. Optional: paste a live Slack snippet in the rail

## How judges run it

```bash
git clone https://github.com/ankukumarsingh82-boop/cerebro-arclens.git
cd cerebro-arclens
./run.sh
# tests: .venv/bin/python -m pytest -q
```

No secrets. No cloud model. Python 3.11+ is enough.

## Architecture

```
export → parser (WhatsApp / Slack / JSON / generic)
      → per-turn VADER polarity + emotion lexicon + sarcasm heuristics
      → smoothed emotion arc + speaker deltas
      → escalation rules (cliff, cascade, sarcasm cluster, rupture)
      → FastAPI JSON + static UI (vendored Chart.js)
```

## Built vs. out of scope

| In the MVP | Not in this drop |
| --- | --- |
| Chat upload + four samples | Live WhatsApp/Slack OAuth |
| Per-turn tone + sarcasm/irony cues | Fine-tuned transformer weights |
| Emotion-arc chart + alerts | Multi-lingual models |
| Tests + `run.sh` + local-first NLP | Hosted inference / API keys |

## Success bar (from the brief)

End-to-end on a sample multi-turn chat: **yes** (`slack_incident.txt`). README: **yes**. No secrets in the repo: **yes** (enforced in `tests/test_no_secrets.py`).
