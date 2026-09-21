from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Sarcasm(BaseModel):
    flag: bool
    score: float = Field(ge=0.0, le=1.0)
    irony: bool = False
    cues: list[str] = Field(default_factory=list)


class Tone(BaseModel):
    label: str
    polarity: float = Field(ge=-1.0, le=1.0)
    intensity: float = Field(ge=0.0, le=1.0)
    emotions: dict[str, float]
    sarcasm: Sarcasm
    confidence: float = Field(ge=0.0, le=1.0)


class Turn(BaseModel):
    index: int
    timestamp: str | None = None
    speaker: str
    text: str
    tone: Tone


class ArcPoint(BaseModel):
    t: int
    polarity: float
    smoothed: float
    speaker: str
    label: str


class SpeakerArc(BaseModel):
    speaker: str
    mean_polarity: float
    delta: float
    turn_count: int


class ArcSummary(BaseModel):
    start: float
    end: float
    delta: float
    volatility: float
    mean: float
    lowest_turn: int
    highest_turn: int
    speakers: list[SpeakerArc]


class Arc(BaseModel):
    points: list[ArcPoint]
    summary: ArcSummary


class Alert(BaseModel):
    id: str
    severity: Literal["info", "warning", "critical"]
    kind: str
    at_turn: int
    window: list[int]
    title: str
    detail: str


class Meta(BaseModel):
    source: str
    format: str
    turn_count: int
    speakers: list[str]
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)


class Analysis(BaseModel):
    meta: Meta
    turns: list[Turn]
    arc: Arc
    alerts: list[Alert]


class SampleInfo(BaseModel):
    name: str
    title: str
    format: str
    bytes: int
    preview: str


class AnalyzeTextRequest(BaseModel):
    text: str
    filename: str | None = None
