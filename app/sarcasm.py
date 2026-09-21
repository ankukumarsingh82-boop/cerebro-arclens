from __future__ import annotations

import re

from app.lexicon import (
    NEGATIVE_EMOJIS,
    NEGATIVE_SURFACE,
    POSITIVE_EMOJIS,
    POSITIVE_SURFACE,
    SARCASM_EMOJIS,
    SARCASM_PHRASES,
)


_WORD = re.compile(r"[A-Za-z']+")
_QUOTED = re.compile(r'["“]([^"”]{1,24})["”]')


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _WORD.findall(text)]


def score_sarcasm(text: str, previous_text: str | None = None) -> dict:
    """Return interpretable sarcasm/irony scores. Local heuristics only."""
    original = text.strip()
    low = original.lower()
    tokens = _tokens(original)
    token_set = set(tokens)
    cues: list[str] = []
    score = 0.0
    irony = False

    for phrase, weight, cue in SARCASM_PHRASES:
        if phrase in low:
            score += weight
            cues.append(cue)

    pos_hits = [t for t in tokens if t in POSITIVE_SURFACE]
    neg_hits = [t for t in tokens if t in NEGATIVE_SURFACE]
    if pos_hits and neg_hits:
        score += 0.42
        irony = True
        cues.append("contrastive polarity")

    quoted = [q.lower() for q in _QUOTED.findall(original)]
    if any(q in POSITIVE_SURFACE or q in {"fine", "sure", "great", "ok", "okay"} for q in quoted):
        score += 0.38
        cues.append("quoted dismissal")

    if original.endswith("...") and pos_hits:
        score += 0.28
        cues.append("trailing ellipsis after praise")

    bangs = original.count("!")
    if bangs >= 2 and (neg_hits or "great" in token_set or "perfect" in token_set):
        score += min(0.22, 0.08 * bangs)
        cues.append("punctuated heat")

    for emoji, weight in SARCASM_EMOJIS.items():
        if emoji in original:
            score += weight
            cues.append(f"emoji {emoji}")

    has_pos_emoji = any(e in original for e in POSITIVE_EMOJIS)
    has_neg_emoji = any(e in original for e in NEGATIVE_EMOJIS)
    if has_pos_emoji and (neg_hits or (previous_text and any(w in previous_text.lower() for w in NEGATIVE_SURFACE))):
        score += 0.34
        irony = True
        cues.append("positive emoji on a dark turn")
    if has_neg_emoji and pos_hits:
        score += 0.3
        irony = True
        cues.append("negative emoji on praise")

    # Reply sarcasm: upbeat surface after a complaint.
    if previous_text:
        prev_low = previous_text.lower()
        prev_neg = any(w in prev_low for w in NEGATIVE_SURFACE) or any(
            p in prev_low for p in ("forgot", "late", "alone", "down", "error", "fail")
        )
        this_pos = bool(pos_hits) or low.startswith(("wow", "great", "nice", "love", "perfect", "sure"))
        if prev_neg and this_pos and len(tokens) <= 16:
            score += 0.36
            irony = True
            cues.append("upbeat reply to a complaint")

    # "Definitely" deadpan without the full phrase.
    if "definitely" in token_set and ("nothing" in token_set or "forgot" in token_set or "needed" in token_set):
        score += 0.3
        cues.append("deadpan definitely")

    # Dedup cues, cap score.
    seen: list[str] = []
    for cue in cues:
        if cue not in seen:
            seen.append(cue)
    score = max(0.0, min(1.0, score))
    # Irony can exist slightly below the sarcasm threshold.
    if pos_hits and neg_hits:
        irony = True
    flag = score >= 0.55
    if flag:
        irony = True
    return {
        "flag": flag,
        "score": round(score, 3),
        "irony": irony,
        "cues": seen[:6],
    }
