from pathlib import Path

from app.parsers import parse_chat, parse_path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def test_whatsapp_skips_encryption_and_system_lines():
    parsed = parse_path(DATA / "whatsapp_dinner.txt")
    assert parsed.format == "whatsapp"
    speakers = {t.speaker for t in parsed.turns}
    assert speakers == {"Riya", "Arjun"}
    assert all("end-to-end encrypted" not in t.text.lower() for t in parsed.turns)
    assert parsed.turns[0].text.startswith("I'm at the restaurant")


def test_whatsapp_multiline_continuation():
    blob = (
        "12/6/24, 7:02 PM - Riya: first line\n"
        "still riya\n"
        "12/6/24, 7:03 PM - Arjun: reply\n"
    )
    parsed = parse_chat(blob, filename="whatsapp.txt")
    assert parsed.format == "whatsapp"
    assert parsed.turns[0].text == "first line\nstill riya"
    assert parsed.turns[1].speaker == "Arjun"


def test_slack_two_line_headers():
    parsed = parse_path(DATA / "slack_incident.txt")
    assert parsed.format == "slack"
    assert parsed.turns[0].speaker == "marco"
    assert "feeling confident" in parsed.turns[0].text
    assert parsed.turns[-1].speaker == "priya"


def test_json_export():
    parsed = parse_path(DATA / "json_standup.json")
    assert parsed.format == "json"
    assert [t.speaker for t in parsed.turns] == ["Dev", "Sam", "Dev", "Sam", "Priya", "Dev"]


def test_generic_speaker_colon():
    parsed = parse_chat("Ada: hello there\nBea: oh great, hello\n", filename="notes.txt")
    assert parsed.format == "generic"
    assert len(parsed.turns) == 2
    assert parsed.turns[0].speaker == "Ada"


def test_ios_whatsapp_brackets():
    blob = "[12/06/2024, 19:02:11] Riya: Did you forget again?\n"
    parsed = parse_chat(blob, filename="chat.txt")
    assert parsed.format == "whatsapp"
    assert parsed.turns[0].speaker == "Riya"
