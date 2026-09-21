# ArcLens

**Cerebro PS-01 · Tone intelligence MVP**

Upload a WhatsApp / Slack-style chat export. ArcLens scores **every turn** for tone and sarcasm/irony, draws the **emotion arc**, and raises **escalation alerts** when the room starts to break.

Local-first. No API keys. Chats never leave the machine that runs it.

Prize track: ₹5,000 · online · prefer IEM floor Nov 2–4 2026 if that calendar is the one that counts.

## Quick start

```bash
git clone https://github.com/ankukumarsingh82-boop/cerebro-arclens.git
cd cerebro-arclens
./run.sh
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) (or [/?demo=1](http://127.0.0.1:8000/?demo=1) to skip the empty state). Click **Run incident demo** (or pick a sample in the rail). You should see:

1. A polarity arc that falls as the incident heats up
2. Per-turn chips for tone + sarcasm cues
3. Cliff / cascade / rupture alerts you can click to jump the thread

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Copy `.env.example` → `.env` only if you need to change host/port. Defaults need no secrets.

## What it does

| Step | What you get |
| --- | --- |
| Parse | WhatsApp Android/iOS export, Slack paste (`name [time]` + body), JSON `{messages:[…]}`, or `Speaker: text` |
| Tone | VADER polarity + bundled emotion lexicon → label (furious → warm) |
| Sarcasm / irony | Interpretable cues: stock phrases, contrastive polarity, quoted dismissal, emoji mismatch, upbeat replies to a complaint |
| Emotion arc | Raw polarity, 3-turn smoothed curve, per-speaker delta, volatility |
| Alerts | Cliffs, negative cascades, sarcasm clusters, rupture language (`done covering`, chargebacks, PII, …) |

The chart is the product: escalation is a **slope**, not a single insult.

## Sample threads (`/data`)

- `slack_incident.txt` — green deploy → 5xx → sarcasm → legal/PII. Cliffs.
- `whatsapp_dinner.txt` — late partner, mock-polite heat, “I'm done covering…”
- `support_refund.txt` — billing duplicate, coupon offered, chargeback threat
- `json_standup.json` — mostly warm standup with one dry joke (control sample)

## HTTP API

- `GET /` — UI
- `GET /health`
- `GET /api/samples`
- `GET /api/samples/{name}`
- `POST /api/analyze` — multipart file
- `POST /api/analyze-text` — `{"text":"…","filename":"paste.txt"}`
- `GET /docs` — OpenAPI

Example:

```bash
curl -s http://127.0.0.1:8000/api/samples/slack_incident.txt | python -m json.tool | head
```

Each turn looks like:

```json
{
  "index": 6,
  "speaker": "marco",
  "text": "Oh great. Just what we needed an hour before the investor demo.",
  "tone": {
    "label": "sarcastic",
    "polarity": -0.21,
    "sarcasm": {
      "flag": true,
      "score": 0.78,
      "irony": true,
      "cues": ["stock phrase"]
    }
  }
}
```

## Why local NLP (not a hosted transformer)

Judges should be able to clone and run without tokens, GPUs, or a model download. ArcLens uses **VADER** plus small bundled lexicons so every sarcasm flag can point at a cue. `ARCLENS_USE_TRANSFORMERS=1` is reserved in `.env.example` and does not pull weights in this MVP.

Chart.js v4.4.7 is vendored at `static/vendor/chart.umd.min.js` (MIT) so the timeline works offline.

## Layout

```
app/          FastAPI, parsers, NLP, arc/alerts
data/         sample exports
static/       UI + vendored Chart.js
tests/        parsers, sarcasm, escalation, API, no-secrets
run.sh        venv + install + uvicorn
SUBMIT.md     judge packet
```

## Privacy

Uploads are processed in memory and discarded when the response is sent. Nothing is written back to disk. Do not commit real customer exports.

## License

Demo code for Cerebro PS-01. Chart.js remains MIT, VADER remains its own MIT license via PyPI.
