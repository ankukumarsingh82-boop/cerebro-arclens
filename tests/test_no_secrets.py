from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BANNED = (
    "sk-proj-",
    "sk-ant-",
    "ghp_",
    "xoxb-",
    "AKIA",
    "BEGIN RSA PRIVATE KEY",
    "OPENAI_API_KEY=",
    "HUGGINGFACEHUB_API_TOKEN=",
)


def test_repo_has_no_secrets():
    skip_parts = {".git", ".venv", "vendor", "__pycache__", ".pytest_cache"}
    hits = []
    for path in ROOT.rglob("*"):
        if any(part in skip_parts for part in path.parts):
            continue
        if path.name == "test_no_secrets.py":
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() in {".png", ".jpg", ".woff", ".woff2"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for token in BANNED:
            if token in text:
                hits.append(f"{path.relative_to(ROOT)} contains {token}")
    assert hits == []
