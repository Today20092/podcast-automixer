from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

WAVEFORM_POINT_LIMIT = 512
_CHUNK_FRAMES = 65_536


def _peak_envelope(samples: np.ndarray, point_count: int, scale: float) -> list[list[float]]:
    edges = np.linspace(0, len(samples), point_count + 1, dtype=np.int64)
    return [
        [
            round(float(np.min(samples[edges[i] : edges[i + 1]])) / scale, 6),
            round(float(np.max(samples[edges[i] : edges[i + 1]])) / scale, 6),
        ]
        for i in range(point_count)
    ]


def analyze_comparison_waveforms(
    original_paths: list[Path],
    automixed_paths: list[Path],
    start_seconds: float,
    duration_seconds: float,
    point_limit: int = WAVEFORM_POINT_LIMIT,
) -> dict[str, Any]:
    """Return bounded Original, Automixed, and Difference peak envelopes."""
    if not original_paths or not automixed_paths or point_limit < 1:
        raise ValueError("Comparison waveforms require both programs")
    originals = [sf.read(path, dtype="float32", always_2d=False)[0] for path in original_paths]
    automixed = [sf.read(path, dtype="float32", always_2d=False)[0] for path in automixed_paths]
    with sf.SoundFile(original_paths[0]) as source:
        samplerate = source.samplerate
    start = round(start_seconds * samplerate)
    frames = max(1, round(duration_seconds * samplerate))
    original = np.sum([samples[start : start + frames] for samples in originals], axis=0)
    processed = np.sum([samples[:frames] for samples in automixed], axis=0)
    count = min(len(original), len(processed))
    original, processed = original[:count], processed[:count]
    difference = processed - original
    scale = max(float(np.max(np.abs(original))), float(np.max(np.abs(processed))), 1.0)
    points = min(point_limit, count)
    return {
        "duration_seconds": count / samplerate,
        "point_limit": point_limit,
        "original": _peak_envelope(original, points, scale),
        "automixed": _peak_envelope(processed, points, scale),
        "difference": _peak_envelope(difference, points, scale),
    }


def analyze_monitoring_waveform(
    paths: list[Path], point_limit: int = WAVEFORM_POINT_LIMIT
) -> dict[str, Any]:
    """Stream a bounded signed envelope of the Original Monitoring Mix."""
    if not paths or point_limit < 1:
        raise ValueError("A Recording Set and positive waveform point limit are required")

    sources = [sf.SoundFile(path) for path in paths]
    try:
        samplerate = sources[0].samplerate
        total_frames = min(source.frames for source in sources)
        if total_frames < 1:
            raise ValueError("Waveform unavailable for an empty Recording Set")
        if any(source.samplerate != samplerate or source.channels != 1 for source in sources):
            raise ValueError("Waveform requires synchronized mono recordings")

        point_count = min(point_limit, total_frames)
        minimum = np.full(point_count, np.inf, dtype=np.float32)
        maximum = np.full(point_count, -np.inf, dtype=np.float32)
        offset = 0
        while offset < total_frames:
            count = min(_CHUNK_FRAMES, total_frames - offset)
            chunks = [source.read(count, dtype="float32", always_2d=False) for source in sources]
            actual = min(len(chunk) for chunk in chunks)
            if not actual:
                break
            monitoring_mix = np.sum([chunk[:actual] for chunk in chunks], axis=0)
            bins = ((np.arange(actual, dtype=np.int64) + offset) * point_count) // total_frames
            np.minimum.at(minimum, bins, monitoring_mix)
            np.maximum.at(maximum, bins, monitoring_mix)
            offset += actual

        if offset != total_frames or np.any(~np.isfinite(minimum)):
            raise ValueError("Waveform unavailable because the Recording Set could not be read")
        peak = max(float(np.max(np.abs(minimum))), float(np.max(np.abs(maximum))), 1.0)
        points = np.column_stack((minimum / peak, maximum / peak))
        return {
            "program": "original_monitoring_mix",
            "duration_seconds": total_frames / samplerate,
            "points": [[round(float(low), 6), round(float(high), 6)] for low, high in points],
        }
    finally:
        for source in sources:
            source.close()
