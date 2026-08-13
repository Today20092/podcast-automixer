from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


def _envelope(values: np.ndarray, bins: int) -> list[list[float]]:
    edges = np.linspace(0, len(values), min(bins, len(values)) + 1, dtype=int)
    return [
        [float(values[a:b].min()), float(values[a:b].max())]
        for a, b in zip(edges[:-1], edges[1:], strict=True)
    ]


def _levels(values: np.ndarray) -> list[list[list[float]]]:
    levels = []
    bins = min(2048, len(values))
    while bins >= 32:
        levels.append(_envelope(values, bins))
        bins //= 4
    return levels or [_envelope(values, max(1, len(values)))]


def build_diagnostic_timeline(
    original: Path, automixed: Path, report_path: Path, start: float, duration: float
) -> dict[str, Any]:
    """Build the cached, display-only tracer for one Preview Run microphone."""
    report = json.loads(report_path.read_text(encoding="utf-8"))
    data = report.get("diagnostic_timeline")
    if not isinstance(data, dict):
        raise ValueError("Preview Run does not contain Diagnostic Timeline evidence")
    source, rate = sf.read(
        original,
        start=round(start * sf.info(original).samplerate),
        frames=round(duration * sf.info(original).samplerate),
        dtype="float32",
    )
    rendered, rendered_rate = sf.read(automixed, dtype="float32")
    if rate != rendered_rate:
        raise ValueError("Preview Run waveform rates do not match")
    if source.ndim > 1:
        source = source.mean(axis=1)
    if rendered.ndim > 1:
        rendered = rendered.mean(axis=1)
    count = min(len(source), len(rendered))
    source = np.asarray(source[:count])
    rendered = np.asarray(rendered[:count])
    return {
        "recording_identity": str(original.resolve()),
        "preview_range": {"start_seconds": start, "duration_seconds": duration},
        "duration_seconds": duration,
        "db_domain": {"minimum": -60.0, "maximum": 0.0},
        "waveform_levels": _levels(source),
        "gain_adjusted_waveform_levels": _levels(rendered),
        "speech_evidence": data["speech_evidence"][0],
        "automix_target": data["automix_target"][0],
        "applied_gain_db": data["applied_gain_db"][0],
        "frame_ms": data["frame_ms"],
        "evidence_gaps": [],
    }
