from __future__ import annotations

import re

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.lexicon import EMOTIONS, INTENSIFIERS, NEGATORS
from app.sarcasm import score_sarcasm

_WORD = re.compile(r"[A-Za-z']+")
_analyzer = SentimentIntensityAnalyzer()


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _WORD.findall(text)]


def _emotion_scores(tokens: list[str]) -> dict[str, float]:
    raw: dict[str, float] = {name: 0.0 for name in EMOTIONS}
    if not tokens:
        return raw
    for i, tok in enumerate(tokens):
        negated = False
        window = tokens[max(0, i - 3) : i]
        if any(w in NEGATORS for w in window):
            negated = True
        boost = 1.0
        for w in window:
            if w in INTENSIFIERS:
                boost += INTENSIFIERS[w]
        for emotion, vocab in EMOTIONS.items():
            if tok in vocab:
                delta = boost
                target = emotion
                if negated:
                    if emotion == "joy":
                        target = "sadness"
                    elif emotion == "trust":
                        target = "anger"
                    elif emotion == "anger":
                        target = "trust"
                    else:
                        delta *= 0.35
                raw[target] += delta
    total = sum(raw.values())
    if total <= 0:
        return {k: 0.0 for k in raw}
    return {k: round(v / total, 3) for k, v in raw.items()}


def _label(polarity: float, intensity: float, emotions: dict[str, float], sarcasm: dict) -> str:
    if sarcasm["flag"]:
        return "sarcastic"
    ranked = sorted(emotions.items(), key=lambda kv: kv[1], reverse=True)
    top, top_s = ranked[0] if ranked else ("neutral", 0.0)
    second = ranked[1][0] if len(ranked) > 1 else "neutral"

    if polarity <= -0.55 and (top == "anger" or intensity >= 0.7):
        return "furious" if intensity >= 0.78 or polarity <= -0.75 else "angry"
    if polarity <= -0.28 and top in {"anger", "disgust"}:
        return "frustrated"
    if top == "fear" and (polarity < 0.1 or top_s >= 0.3):
        return "anxious"
    if top == "sadness" and polarity <= 0.05:
        return "sad"
    if polarity <= -0.18:
        return "tense"
    if polarity >= 0.45 and top in {"joy", "anticipation"}:
        return "excited"
    if polarity >= 0.22 and top in {"trust", "joy"}:
        return "supportive"
    if polarity >= 0.18:
        return "warm"
    if top == "surprise" or second == "surprise":
        return "alert"
    if top == "anticipation":
        return "forward-looking"
    return "neutral"


def analyze_text(text: str, previous_text: str | None = None) -> dict:
    blob = (text or "").strip()
    tokens = _tokens(blob)
    vader = _analyzer.polarity_scores(blob or " ")
    polarity = float(vader["compound"])
    # Intensity blends VADER magnitude with surface heat.
    bangs = blob.count("!") + blob.count("?")
    caps = sum(1 for c in blob if c.isupper())
    cap_ratio = caps / max(1, sum(1 for c in blob if c.isalpha()))
    intensity = min(
        1.0,
        abs(polarity) * 0.75
        + min(0.2, bangs * 0.04)
        + (0.12 if cap_ratio > 0.45 and len(tokens) > 2 else 0.0)
        + float(vader["pos"] + vader["neg"]) * 0.15,
    )
    sarcasm = score_sarcasm(blob, previous_text)
    # Surface-positive sarcasm often fools lexicon polarity; tilt it down a little.
    if sarcasm["flag"] and polarity > 0:
        polarity = max(-0.45, polarity - 0.55 * sarcasm["score"])
    elif sarcasm["flag"] and polarity > -0.15:
        polarity = polarity - 0.2 * sarcasm["score"]
    polarity = max(-1.0, min(1.0, polarity))
    emotions = _emotion_scores(tokens)
    if sarcasm["flag"]:
        emotions["disgust"] = round(min(1.0, emotions.get("disgust", 0.0) + 0.15), 3)
    label = _label(polarity, intensity, emotions, sarcasm)
    # Confidence: short/empty turns are guesses.
    if len(tokens) <= 1:
        confidence = 0.28 + 0.15 * abs(polarity)
    else:
        confidence = 0.4 + 0.25 * min(1.0, len(tokens) / 10) + 0.25 * abs(polarity) + 0.15 * sarcasm["score"]
    confidence = max(0.15, min(0.95, confidence))
    return {
        "label": label,
        "polarity": round(polarity, 3),
        "intensity": round(intensity, 3),
        "emotions": emotions,
        "sarcasm": sarcasm,
        "confidence": round(confidence, 3),
    }


def maybe_transformer_note() -> str | None:
    """MVP stays local-first. Optional transformers are documented, not required."""
    from app.config import USE_TRANSFORMERS

    if not USE_TRANSFORMERS:
        return None
    return "ARCLENS_USE_TRANSFORMERS is set, but the MVP still uses the local engine (no model download)."
