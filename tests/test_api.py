from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
DATA = Path(__file__).resolve().parents[1] / "data"


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["local_first"] is True


def test_index_serves_ui():
    res = client.get("/")
    assert res.status_code == 200
    assert "ArcLens" in res.text
    assert "/static/app.js" in res.text


def test_chart_js_is_vendored():
    res = client.get("/static/vendor/chart.umd.min.js")
    assert res.status_code == 200
    assert "Chart" in res.text


def test_samples_list_and_analyze():
    res = client.get("/api/samples")
    assert res.status_code == 200
    names = {s["name"] for s in res.json()}
    assert "slack_incident.txt" in names
    assert "whatsapp_dinner.txt" in names
    analysis = client.get("/api/samples/slack_incident.txt")
    assert analysis.status_code == 200
    payload = analysis.json()
    assert payload["turns"]
    assert payload["arc"]["points"]
    assert payload["alerts"]


def test_upload_and_paste_endpoints():
    chat = DATA / "support_refund.txt"
    upload = client.post("/api/analyze", files={"file": ("support_refund.txt", chat.read_bytes(), "text/plain")})
    assert upload.status_code == 200
    assert upload.json()["meta"]["turn_count"] >= 8

    paste = client.post(
        "/api/analyze-text",
        json={"text": "Sam: lgtm, thanks\nPriya: oh great. just what we needed", "filename": "paste.txt"},
    )
    assert paste.status_code == 200
    assert paste.json()["turns"][1]["tone"]["sarcasm"]["flag"] is True


def test_unknown_sample_404():
    res = client.get("/api/samples/missing_chat.txt")
    assert res.status_code == 404
