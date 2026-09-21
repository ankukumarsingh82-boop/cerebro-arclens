from __future__ import annotations

import statistics

from app.lexicon import THREAT_PHRASES
from app.schemas import Alert, Arc, ArcPoint, ArcSummary, SpeakerArc, Turn


def rolling_mean(values: list[float], window: int = 3) -> list[float]:
    out: list[float] = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        chunk = values[start : i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def build_arc(turns: list[Turn]) -> Arc:
    if not turns:
        empty = ArcSummary(
            start=0.0,
            end=0.0,
            delta=0.0,
            volatility=0.0,
            mean=0.0,
            lowest_turn=0,
            highest_turn=0,
            speakers=[],
        )
        return Arc(points=[], summary=empty)

    polarities = [t.tone.polarity for t in turns]
    smoothed = rolling_mean(polarities, window=3)
    points = [
        ArcPoint(
            t=t.index,
            polarity=t.tone.polarity,
            smoothed=round(smoothed[i], 3),
            speaker=t.speaker,
            label=t.tone.label,
        )
        for i, t in enumerate(turns)
    ]
    lowest = min(range(len(polarities)), key=lambda i: polarities[i])
    highest = max(range(len(polarities)), key=lambda i: polarities[i])
    mean = sum(polarities) / len(polarities)
    volatility = statistics.pstdev(polarities) if len(polarities) > 1 else 0.0

    speakers: list[SpeakerArc] = []
    names = []
    for t in turns:
        if t.speaker not in names:
            names.append(t.speaker)
    for name in names:
        sp = [t.tone.polarity for t in turns if t.speaker == name]
        speakers.append(
            SpeakerArc(
                speaker=name,
                mean_polarity=round(sum(sp) / len(sp), 3),
                delta=round(sp[-1] - sp[0], 3),
                turn_count=len(sp),
            )
        )

    summary = ArcSummary(
        start=round(polarities[0], 3),
        end=round(polarities[-1], 3),
        delta=round(polarities[-1] - polarities[0], 3),
        volatility=round(volatility, 3),
        mean=round(mean, 3),
        lowest_turn=lowest,
        highest_turn=highest,
        speakers=speakers,
    )
    return Arc(points=points, summary=summary)


def _threats_in(text: str) -> list[str]:
    low = text.lower()
    return [p for p in THREAT_PHRASES if p in low]


def detect_alerts(turns: list[Turn], arc: Arc) -> list[Alert]:
    alerts: list[Alert] = []
    if len(turns) < 2:
        return alerts

    smoothed = [p.smoothed for p in arc.points]
    polarities = [t.tone.polarity for t in turns]

    # Cliff: sharp drop in the smoothed arc.
    window = 4
    for i in range(1, len(smoothed)):
        j = max(0, i - window)
        drop = smoothed[j] - smoothed[i]
        if drop >= 0.4 and polarities[i] < -0.15:
            severity = "critical" if drop >= 0.55 or polarities[i] <= -0.55 else "warning"
            alerts.append(
                Alert(
                    id=f"cliff-{i}",
                    severity=severity,
                    kind="cliff",
                    at_turn=i,
                    window=[j, i],
                    title="Emotion-arc cliff",
                    detail=(
                        f"Smoothed polarity dropped {drop:.2f} between turns {j + 1} and {i + 1} "
                        f"({turns[i].speaker}: “{_clip(turns[i].text)}”)."
                    ),
                )
            )

    # Cascade: consecutive negative, mostly falling.
    run_start = None
    for i, p in enumerate(polarities):
        if p <= -0.22:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None and i - run_start >= 3:
                _add_cascade(alerts, turns, polarities, run_start, i - 1)
            run_start = None
    if run_start is not None and len(polarities) - run_start >= 3:
        _add_cascade(alerts, turns, polarities, run_start, len(polarities) - 1)

    # Sarcasm cluster.
    sarc_idx = [t.index for t in turns if t.tone.sarcasm.flag]
    if len(sarc_idx) >= 2:
        # group nearby
        cluster = [sarc_idx[0]]
        for idx in sarc_idx[1:]:
            if idx - cluster[-1] <= 3:
                cluster.append(idx)
            else:
                _add_sarcasm_cluster(alerts, turns, cluster)
                cluster = [idx]
        _add_sarcasm_cluster(alerts, turns, cluster)

    # Threat / rupture language.
    for t in turns:
        hits = _threats_in(t.text)
        if not hits:
            continue
        critical = any(
            h in hits
            for h in (
                "lawsuit",
                "chargeback",
                "chargebacks",
                "pii leaked",
                "i am done",
                "i'm done",
                "im done",
                "i quit",
                "done covering",
                "i cannot do this again",
                "i can't do this again",
            )
        ) or t.tone.polarity <= -0.5
        alerts.append(
            Alert(
                id=f"rupture-{t.index}",
                severity="critical" if critical else "warning",
                kind="rupture",
                at_turn=t.index,
                window=[max(0, t.index - 1), t.index],
                title="Rupture language",
                detail=(
                    f"{t.speaker} used high-stakes wording ({', '.join(hits[:3])}) "
                    f"at turn {t.index + 1}."
                ),
            )
        )

    # Volatility spike vs early baseline.
    if len(polarities) >= 8:
        early = polarities[: max(3, len(polarities) // 3)]
        late = polarities[-max(3, len(polarities) // 3) :]
        early_v = statistics.pstdev(early) if len(early) > 1 else 0.0
        late_v = statistics.pstdev(late) if len(late) > 1 else 0.0
        if late_v >= 0.28 and late_v > early_v + 0.12:
            alerts.append(
                Alert(
                    id="volatility-late",
                    severity="info",
                    kind="volatility",
                    at_turn=len(turns) - 1,
                    window=[len(turns) - len(late), len(turns) - 1],
                    title="Room got noisier",
                    detail=(
                        f"Late-thread volatility {late_v:.2f} vs early {early_v:.2f}. "
                        "The conversation is swinging harder than it started."
                    ),
                )
            )

    return _dedupe(alerts)


def _clip(text: str, n: int = 88) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= n else compact[: n - 1] + "…"


def _add_cascade(alerts: list[Alert], turns: list[Turn], polarities: list[float], start: int, end: int) -> None:
    span = polarities[start : end + 1]
    falling = sum(1 for a, b in zip(span, span[1:]) if b <= a + 0.02)
    severity: str = "warning"
    if end - start + 1 >= 4 and span[-1] <= -0.45:
        severity = "critical"
    elif falling >= max(2, len(span) - 2) and span[-1] < span[0]:
        severity = "critical" if span[-1] <= -0.4 else "warning"
    alerts.append(
        Alert(
            id=f"cascade-{start}-{end}",
            severity=severity,
            kind="cascade",
            at_turn=end,
            window=[start, end],
            title="Negative cascade",
            detail=(
                f"{end - start + 1} consecutive tense/negative turns "
                f"({turns[start].speaker} → {turns[end].speaker}), "
                f"ending at polarity {span[-1]:.2f}."
            ),
        )
    )


def _add_sarcasm_cluster(alerts: list[Alert], turns: list[Turn], cluster: list[int]) -> None:
    if len(cluster) < 2:
        return
    last = cluster[-1]
    speakers = sorted({turns[i].speaker for i in cluster})
    alerts.append(
        Alert(
            id=f"sarcasm-{cluster[0]}-{last}",
            severity="warning" if len(cluster) >= 3 else "info",
            kind="sarcasm-cluster",
            at_turn=last,
            window=[cluster[0], last],
            title="Sarcasm cluster",
            detail=(
                f"{len(cluster)} sarcastic/ironic turns close together "
                f"({', '.join(speakers)}). Heat often hides in the joke."
            ),
        )
    )


def _dedupe(alerts: list[Alert]) -> list[Alert]:
    rank = {"critical": 3, "warning": 2, "info": 1}
    alerts_sorted = sorted(alerts, key=lambda a: (-rank[a.severity], a.at_turn, a.kind))
    kept: list[Alert] = []
    used_ids: set[str] = set()
    for alert in alerts_sorted:
        if alert.id in used_ids:
            continue
        overlap = False
        for prev in kept:
            if prev.kind != alert.kind:
                continue
            if _windows_overlap(prev.window, alert.window):
                overlap = True
                break
        if overlap:
            continue
        used_ids.add(alert.id)
        kept.append(alert)
    kept.sort(key=lambda a: (a.at_turn, -rank[a.severity]))
    return kept


def _windows_overlap(a: list[int], b: list[int]) -> bool:
    return not (a[-1] < b[0] or b[-1] < a[0])
