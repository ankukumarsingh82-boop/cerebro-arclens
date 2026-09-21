from __future__ import annotations

from pathlib import Path

from app.config import DATA_DIR, MAX_TURNS
from app.nlp import analyze_text, maybe_transformer_note
from app.parsers import parse_chat, parse_path
from app.arc import build_arc, detect_alerts
from app.schemas import Analysis, Meta, SampleInfo, Tone, Turn, Sarcasm


def _to_turn(index: int, timestamp: str | None, speaker: str, text: str, previous_text: str | None) -> Turn:
    raw = analyze_text(text, previous_text)
    return Turn(
        index=index,
        timestamp=timestamp,
        speaker=speaker,
        text=text,
        tone=Tone(
            label=raw["label"],
            polarity=raw["polarity"],
            intensity=raw["intensity"],
            emotions=raw["emotions"],
            sarcasm=Sarcasm(**raw["sarcasm"]),
            confidence=raw["confidence"],
        ),
    )


def analyze_parsed(parsed, source: str) -> Analysis:
    warnings = list(parsed.warnings)
    raw_turns = parsed.turns[:MAX_TURNS]
    truncated = len(parsed.turns) > MAX_TURNS
    if truncated:
        warnings.append(f"Truncated to {MAX_TURNS} turns")
    note = maybe_transformer_note()
    if note:
        warnings.append(note)

    turns: list[Turn] = []
    prev_text = None
    for i, raw in enumerate(raw_turns):
        turns.append(_to_turn(i, raw.timestamp, raw.speaker, raw.text, prev_text))
        prev_text = raw.text

    speakers: list[str] = []
    for t in turns:
        if t.speaker not in speakers:
            speakers.append(t.speaker)

    arc = build_arc(turns)
    alerts = detect_alerts(turns, arc)
    meta = Meta(
        source=source,
        format=parsed.format,
        turn_count=len(turns),
        speakers=speakers,
        truncated=truncated,
        warnings=warnings,
    )
    return Analysis(meta=meta, turns=turns, arc=arc, alerts=alerts)


def analyze_text_blob(text: str, filename: str | None = None) -> Analysis:
    parsed = parse_chat(text, filename=filename)
    source = filename or "paste"
    if not parsed.turns:
        parsed.warnings.append("No turns detected. Try WhatsApp export, Slack paste, JSON, or Speaker: text lines.")
    return analyze_parsed(parsed, source=source)


def analyze_file(path: Path) -> Analysis:
    parsed = parse_path(path)
    return analyze_parsed(parsed, source=path.name)


def list_samples() -> list[SampleInfo]:
    items: list[SampleInfo] = []
    if not DATA_DIR.exists():
        return items
    for path in sorted(DATA_DIR.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        text = path.read_text(encoding="utf-8")
        parsed = parse_chat(text, filename=path.name)
        preview_src = next((t.text for t in parsed.turns if t.text.strip()), text)
        preview = " ".join(preview_src.split())
        if len(preview) > 140:
            preview = preview[:139] + "…"
        title = path.stem.replace("_", " ")
        items.append(
            SampleInfo(
                name=path.name,
                title=title,
                format=parsed.format,
                bytes=path.stat().st_size,
                preview=preview,
            )
        )
    return items
