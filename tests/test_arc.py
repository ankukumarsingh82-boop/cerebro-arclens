from pathlib import Path

from app.engine import analyze_file, analyze_text_blob


DATA = Path(__file__).resolve().parents[1] / "data"


def test_incident_raises_escalation_alerts():
    result = analyze_file(DATA / "slack_incident.txt")
    assert result.meta.turn_count >= 10
    assert result.alerts
    severities = {a.severity for a in result.alerts}
    assert "critical" in severities or "warning" in severities
    kinds = {a.kind for a in result.alerts}
    assert kinds & {"cliff", "cascade", "rupture", "sarcasm-cluster"}
    sarcastic = [t for t in result.turns if t.tone.sarcasm.flag]
    assert sarcastic, "incident sample should contain sarcastic turns"
    early = sum(t.tone.polarity for t in result.turns[:4]) / 4
    late = sum(t.tone.polarity for t in result.turns[-4:]) / 4
    assert late < early


def test_dinner_marks_sarcasm_and_rupture():
    result = analyze_file(DATA / "whatsapp_dinner.txt")
    assert any(t.tone.sarcasm.flag for t in result.turns)
    assert any(a.kind in {"rupture", "cascade", "cliff", "sarcasm-cluster"} for a in result.alerts)


def test_standup_stays_mostly_warm():
    result = analyze_file(DATA / "json_standup.json")
    assert result.arc.summary.mean > -0.15
    critical = [a for a in result.alerts if a.severity == "critical"]
    assert critical == []


def test_paste_generic_roundtrip():
    result = analyze_text_blob("Ada: this is a disaster\nBea: oh great. just what I needed\n", filename="paste.txt")
    assert result.meta.turn_count == 2
    assert result.turns[1].tone.sarcasm.flag
