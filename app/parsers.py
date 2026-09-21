from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

SYSTEM_SNIPPETS = (
    "messages and calls are end-to-end encrypted",
    "this message was deleted",
    "you deleted this message",
    "<media omitted>",
    "image omitted",
    "video omitted",
    "sticker omitted",
    "audio omitted",
    "document omitted",
    "this chat is with a business account",
    "waiting for this message",
)

WA_ANDROID = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}),?\s+"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap][Mm])?)\s+"
    r"[-–—]\s+(?P<speaker>[^:]+):\s?(?P<text>.*)$"
)
WA_IOS = re.compile(
    r"^\[(?P<date>\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}),?\s+"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap][Mm])?)\]\s+"
    r"(?P<speaker>[^:]+):\s?(?P<text>.*)$"
)
WA_SYSTEM = re.compile(
    r"^\[?(?P<date>\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}),?\s+"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APap][Mm])?)\]?\s+"
    r"[-–—]\s+(?P<rest>.+)$"
)
SLACK_HEADER = re.compile(
    r"^(?P<speaker>[A-Za-z][\w.\- ]{0,48}?)\s+\[(?P<time>[^\]]+)\]\s*$"
)
SLACK_INLINE = re.compile(
    r"^(?:\[(?P<time1>[^\]]+)\]\s+)?(?P<speaker>[A-Za-z][\w.\-]{0,40})\s*"
    r"(?:\[(?P<time2>[^\]]+)\])?\s*:\s+(?P<text>.+)$"
)
GENERIC = re.compile(r"^(?P<speaker>[A-Za-z][\w.\- ]{0,40}):\s+(?P<text>.+)$")
TIME_ONLY = re.compile(r"^\[(?P<time>[^\]]+)\]\s+(?P<speaker>[^:]+):\s?(?P<text>.*)$")


@dataclass
class RawTurn:
    timestamp: str | None
    speaker: str
    text: str


@dataclass
class ParsedChat:
    format: str
    turns: list[RawTurn] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _is_system(text: str) -> bool:
    low = text.strip().lower()
    if not low:
        return True
    return any(s in low for s in SYSTEM_SNIPPETS)


def _clean_speaker(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip() or "unknown"


def _stamp(date: str | None, time: str | None) -> str | None:
    if not date and not time:
        return None
    if date and time:
        return f"{date} {time}"
    return date or time


def parse_json_document(text: str) -> ParsedChat | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    messages = None
    if isinstance(payload, dict):
        messages = payload.get("messages") or payload.get("turns") or payload.get("data")
    elif isinstance(payload, list):
        messages = payload
    if not isinstance(messages, list):
        return None
    turns: list[RawTurn] = []
    warnings: list[str] = []
    for item in messages:
        if not isinstance(item, dict):
            warnings.append("skipped a non-object JSON message")
            continue
        speaker = (
            item.get("speaker")
            or item.get("user")
            or item.get("username")
            or item.get("author")
            or item.get("name")
            or "unknown"
        )
        body = item.get("text") or item.get("message") or item.get("body") or item.get("content") or ""
        ts = item.get("timestamp") or item.get("ts") or item.get("time") or item.get("date")
        if isinstance(ts, (int, float)):
            try:
                ts = datetime.fromtimestamp(float(ts)).isoformat(sep=" ", timespec="minutes")
            except (OverflowError, OSError, ValueError):
                ts = str(ts)
        body = str(body).strip()
        if _is_system(body):
            continue
        turns.append(RawTurn(timestamp=str(ts) if ts else None, speaker=_clean_speaker(str(speaker)), text=body))
    return ParsedChat(format="json", turns=turns, warnings=warnings)


def _parse_whatsapp(lines: list[str]) -> list[RawTurn]:
    turns: list[RawTurn] = []
    for line in lines:
        raw = line.rstrip("\n")
        match = WA_ANDROID.match(raw) or WA_IOS.match(raw)
        if match:
            text = match.group("text").strip()
            speaker = _clean_speaker(match.group("speaker"))
            if _is_system(text):
                continue
            turns.append(
                RawTurn(
                    timestamp=_stamp(match.group("date"), match.group("time")),
                    speaker=speaker,
                    text=text,
                )
            )
            continue
        if WA_SYSTEM.match(raw) and ":" not in raw.split(" - ", 1)[-1]:
            continue
        if turns and raw.strip() and not _is_system(raw):
            turns[-1].text = f"{turns[-1].text}\n{raw}".strip()
    return turns


def _parse_slack(lines: list[str]) -> list[RawTurn]:
    turns: list[RawTurn] = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        header = SLACK_HEADER.match(line)
        if header:
            speaker = _clean_speaker(header.group("speaker"))
            ts = header.group("time").strip()
            body_parts: list[str] = []
            i += 1
            while i < len(lines):
                nxt = lines[i].rstrip("\n")
                if SLACK_HEADER.match(nxt) or not nxt.strip():
                    if not nxt.strip() and body_parts:
                        i += 1
                        break
                    if SLACK_HEADER.match(nxt):
                        break
                if nxt.strip():
                    body_parts.append(nxt)
                i += 1
            text = "\n".join(body_parts).strip()
            if text and not _is_system(text):
                turns.append(RawTurn(timestamp=ts, speaker=speaker, text=text))
            continue
        inline = TIME_ONLY.match(line) or SLACK_INLINE.match(line)
        if inline:
            speaker = _clean_speaker(inline.group("speaker"))
            text = inline.group("text").strip()
            ts = None
            for key in ("time", "time1", "time2"):
                if key in inline.re.groupindex and inline.group(key):
                    ts = inline.group(key)
                    break
            if text and not _is_system(text):
                turns.append(RawTurn(timestamp=ts, speaker=speaker, text=text))
            i += 1
            continue
        if turns and line.strip() and not _is_system(line):
            turns[-1].text = f"{turns[-1].text}\n{line}".strip()
        i += 1
    return turns


def _parse_generic(lines: list[str]) -> list[RawTurn]:
    turns: list[RawTurn] = []
    for line in lines:
        raw = line.rstrip("\n")
        match = GENERIC.match(raw)
        if match:
            text = match.group("text").strip()
            if _is_system(text):
                continue
            turns.append(
                RawTurn(timestamp=None, speaker=_clean_speaker(match.group("speaker")), text=text)
            )
            continue
        if turns and raw.strip() and not _is_system(raw):
            turns[-1].text = f"{turns[-1].text}\n{raw}".strip()
    if not turns:
        blob = "\n".join(line.rstrip() for line in lines).strip()
        if blob and not _is_system(blob):
            turns.append(RawTurn(timestamp=None, speaker="speaker", text=blob))
    return turns


def detect_format(text: str, filename: str | None = None) -> str:
    name = (filename or "").lower()
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            json.loads(text)
        except json.JSONDecodeError:
            pass
        else:
            return "json"
    if name.endswith(".json"):
        return "json"
    if "whatsapp" in name or (" - " in text[:500] and (WA_ANDROID.search(text) or WA_IOS.search(text))):
        if any(WA_ANDROID.match(line) or WA_IOS.match(line) for line in text.splitlines()[:40]):
            return "whatsapp"
    lines = text.splitlines()
    wa_hits = sum(1 for line in lines if WA_ANDROID.match(line) or WA_IOS.match(line))
    slack_hits = sum(1 for line in lines if SLACK_HEADER.match(line) or TIME_ONLY.match(line))
    if wa_hits >= max(2, slack_hits):
        return "whatsapp"
    if slack_hits >= 2 or "slack" in name:
        return "slack"
    if wa_hits:
        return "whatsapp"
    return "generic"


def parse_chat(text: str, filename: str | None = None) -> ParsedChat:
    kind = detect_format(text, filename)
    if kind == "json":
        parsed = parse_json_document(text)
        if parsed is not None:
            if not parsed.turns:
                parsed.warnings.append("JSON parsed but no usable messages were found")
            return parsed
        kind = "generic"
    lines = text.splitlines()
    if kind == "whatsapp":
        turns = _parse_whatsapp(lines)
        if not turns:
            turns = _parse_generic(lines)
            return ParsedChat(format="generic", turns=turns, warnings=["WhatsApp pattern failed; used generic parser"])
        return ParsedChat(format="whatsapp", turns=turns)
    if kind == "slack":
        turns = _parse_slack(lines)
        if not turns:
            turns = _parse_generic(lines)
            return ParsedChat(format="generic", turns=turns, warnings=["Slack pattern failed; used generic parser"])
        return ParsedChat(format="slack", turns=turns)
    return ParsedChat(format="generic", turns=_parse_generic(lines))


def parse_path(path: Path) -> ParsedChat:
    return parse_chat(path.read_text(encoding="utf-8"), filename=path.name)
