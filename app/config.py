from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "static"

HOST = os.getenv("ARCLENS_HOST", "127.0.0.1")
PORT = int(os.getenv("ARCLENS_PORT", "8000"))
MAX_TURNS = int(os.getenv("ARCLENS_MAX_TURNS", "2000"))
USE_TRANSFORMERS = os.getenv("ARCLENS_USE_TRANSFORMERS", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
