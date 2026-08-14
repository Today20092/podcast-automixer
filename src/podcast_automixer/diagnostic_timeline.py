from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

COLORS = ("#3b82f6", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16")


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


def _mono(
    path: Path, start: float | None = None, duration: float | None = None
) -> tuple[np.ndarray, int]:
    info = sf.info(path)
    values, rate = sf.read(
        path,
        start=round((start or 0) * info.samplerate),
        frames=-1 if duration is None else round(duration * info.samplerate),
        dtype="float32",
    )
    if values.ndim > 1:
        values = values.mean(axis=1)
    return np.asarray(values), rate


def build_diagnostic_timeline(
    originals: list[Path], automixed: list[Path], report_path: Path, start: float, duration: float
) -> dict[str, Any]:
    """Build display-only Diagnostic Timeline lanes for a complete Recording Set."""
    report = json.loads(report_path.read_text(encoding="utf-8"))
    data = report.get("diagnostic_timeline")
    if not isinstance(data, dict):
        raise ValueError("Preview Run does not contain Diagnostic Timeline evidence")
    if len(originals) != len(automixed):
        raise ValueError("Preview Run waveform counts do not match")
    lanes = []
    for index, (original, output) in enumerate(zip(originals, automixed, strict=True)):
        source, rate = _mono(original, start, duration)
        rendered, rendered_rate = _mono(output)
        if rate != rendered_rate:
            raise ValueError("Preview Run waveform rates do not match")
        count = min(len(source), len(rendered))
        lanes.append(
            {
                "recording_identity": str(original.resolve()),
                "name": original.stem,
                "color": COLORS[index % len(COLORS)],
                "waveform_levels": _levels(source[:count]),
                "gain_adjusted_waveform_levels": _levels(rendered[:count]),
                "speech_evidence": data["speech_evidence"][index],
                "automix_target": data["automix_target"][index],
                "applied_gain_db": data["applied_gain_db"][index],
                "evidence_gaps": [],
            }
        )
    attenuation = float(report.get("settings", {}).get("attenuation_db", -6.0))
    return {
        "preview_range": {"start_seconds": start, "duration_seconds": duration},
        "duration_seconds": duration,
        "frame_ms": data["frame_ms"],
        "db_domain": {"minimum": min(-12.0, attenuation), "maximum": 0.0},
        "lanes": lanes,
    }
