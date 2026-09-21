from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import DATA_DIR, STATIC_DIR
from app.engine import analyze_file, analyze_text_blob, list_samples
from app.schemas import Analysis, AnalyzeTextRequest, SampleInfo

app = FastAPI(
    title="ArcLens",
    description="Cerebro PS-01 — per-turn tone, sarcasm/irony, emotion-arc, escalation alerts.",
    version=__version__,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=500, detail="UI missing")
    return FileResponse(index_path)


@app.get("/health")
def health():
    return {"ok": True, "name": "ArcLens", "version": __version__, "local_first": True}


@app.get("/api/samples", response_model=list[SampleInfo])
def samples():
    return list_samples()


@app.get("/api/samples/{name}", response_model=Analysis)
def sample_analysis(name: str):
    path = (DATA_DIR / name).resolve()
    if not path.is_file() or DATA_DIR.resolve() not in path.parents:
        raise HTTPException(status_code=404, detail="Unknown sample")
    return analyze_file(path)


@app.post("/api/analyze", response_model=Analysis)
async def analyze(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Empty file")
    return analyze_text_blob(text, filename=file.filename or "upload.txt")


@app.post("/api/analyze-text", response_model=Analysis)
def analyze_text_endpoint(payload: AnalyzeTextRequest):
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")
    return analyze_text_blob(payload.text, filename=payload.filename or "paste.txt")
