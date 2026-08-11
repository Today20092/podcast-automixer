from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .core import AudioInfo, Settings


def build_report_insights(active: np.ndarray, gains: np.ndarray, frame_ms: int) -> dict[str, Any]:
    """Summarize frame decisions into episode-scale, display-ready diagnostics."""
    frame_count = active.shape[1]
    frame_seconds = frame_ms / 1000
    duration_seconds = frame_count * frame_seconds
    active_count = active.sum(axis=0)
    single_owner = active_count == 1
    multiple_owner = active_count > 1
    unowned = active_count == 0
    owners = np.where(single_owner, np.argmax(active, axis=0), -1)
    clear_owners = owners[owners >= 0]
    switches = int(np.sum(clear_owners[1:] != clear_owners[:-1]))
    duration_minutes = duration_seconds / 60

    if duration_seconds < 10 * 60:
        window_seconds = 1.0
    elif duration_seconds < 45 * 60:
        window_seconds = 5.0
    elif duration_seconds <= 120 * 60:
        window_seconds = 15.0
    else:
        window_seconds = 30.0
    window_frames = max(1, round(window_seconds / frame_seconds))

    gain_db = 20 * np.log10(np.maximum(gains, 1e-9))
    timeline = []
    for start in range(0, frame_count, window_frames):
        stop = min(start + window_frames, frame_count)
        timeline.append(
            {
                "start_seconds": round(start * frame_seconds, 3),
                "end_seconds": round(stop * frame_seconds, 3),
                "gain_db": [
                    round(float(gain_db[channel, start:stop].mean()), 3) for channel in range(3)
                ],
                "attenuated_percent": [
                    round(float(np.mean(gain_db[channel, start:stop] < -0.5) * 100), 1)
                    for channel in range(3)
                ],
                "overlap_percent": round(float(np.mean(multiple_owner[start:stop]) * 100), 1),
                "unowned_percent": round(float(np.mean(unowned[start:stop]) * 100), 1),
            }
        )

    share_seconds = 60 if duration_seconds < 10 * 60 else 300 if duration_seconds < 45 * 60 else 600
    share_frames = max(1, round(share_seconds / frame_seconds))
    speaker_share = []
    for start in range(0, frame_count, share_frames):
        stop = min(start + share_frames, frame_count)
        size = stop - start
        speaker_share.append(
            {
                "start_seconds": round(start * frame_seconds, 3),
                "end_seconds": round(stop * frame_seconds, 3),
                "track_percent": [
                    round(float(np.sum(owners[start:stop] == channel) * 100 / size), 1)
                    for channel in range(3)
                ],
                "overlap_percent": round(float(np.mean(multiple_owner[start:stop]) * 100), 1),
                "unowned_percent": round(float(np.mean(unowned[start:stop]) * 100), 1),
            }
        )

    track_summary = [
        {
            "exclusive_percent": round(float(np.mean(owners == channel) * 100), 1),
            "active_percent": round(float(np.mean(active[channel]) * 100), 1),
            "mean_gain_db": round(float(gain_db[channel].mean()), 2),
            "maximum_reduction_db": round(float(gain_db[channel].min()), 2),
        }
        for channel in range(3)
    ]

    def runs(mask: np.ndarray, kind: str) -> list[dict[str, Any]]:
        padded = np.pad(mask.astype(np.int8), (1, 1))
        starts = np.flatnonzero(np.diff(padded) == 1)
        stops = np.flatnonzero(np.diff(padded) == -1)
        result = []
        for start, stop in zip(starts, stops, strict=True):
            duration = (int(stop) - int(start)) * frame_seconds
            minimum = 1.0 if kind == "multiple" else 3.0
            if duration < minimum:
                continue
            result.append(
                {
                    "kind": kind,
                    "start_seconds": round(int(start) * frame_seconds, 3),
                    "end_seconds": round(int(stop) * frame_seconds, 3),
                    "duration_seconds": round(duration, 3),
                    "track_indexes": [
                        channel for channel in range(3) if bool(np.any(active[channel, start:stop]))
                    ],
                }
            )
        result.sort(key=lambda item: item["duration_seconds"], reverse=True)
        return result[:4]

    moments = runs(multiple_owner, "multiple") + runs(unowned, "unowned")
    moments.sort(key=lambda item: item["duration_seconds"], reverse=True)
    return {
        "health": {
            "single_owner_percent": round(float(np.mean(single_owner) * 100), 1),
            "multiple_owner_percent": round(float(np.mean(multiple_owner) * 100), 1),
            "unowned_percent": round(float(np.mean(unowned) * 100), 1),
            "switches_per_minute": round(switches / duration_minutes, 1)
            if duration_minutes
            else 0.0,
        },
        "window_seconds": window_seconds,
        "timeline": timeline,
        "speaker_share": speaker_share,
        "track_summary": track_summary,
        "review_moments": moments,
    }


def write_html_report(
    destination: Path,
    infos: list[AudioInfo],
    settings: Settings,
    gains: np.ndarray,
    active: np.ndarray,
    analysis_report: dict[str, Any],
) -> None:
    """Write the interactive report as one self-contained HTML file."""
    bundle_path = Path(__file__).with_name("report.bundle.js")
    if not bundle_path.exists():
        raise RuntimeError("The packaged HTML report bundle is missing.")

    gain_db = 20 * np.log10(np.maximum(gains, 1e-9))
    colors = ("#3b82f6", "#f59e0b", "#10b981")
    payload = {
        "attenuationDb": settings.attenuation_db,
        "openingTimeConstantMs": settings.open_ms,
        "closingTimeConstantMs": settings.close_ms,
        "loudness": analysis_report.get("loudness"),
        **build_report_insights(active, gains, settings.frame_ms),
        "tracks": [
            {
                "id": f"track-{index + 1}",
                "name": info.path.stem,
                "active": float(analysis_report["active_percent"][index]),
                "meanGain": float(gain_db[index].mean()),
                "calibration": float(analysis_report["calibration_db"][index]),
                "noiseFloor": float(analysis_report["noise_floor_db"][index]),
                "minimumGain": float(gain_db[index].min()),
                "color": colors[index],
            }
            for index, info in enumerate(infos)
        ],
    }
    data = json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c")
    bundle = bundle_path.read_text(encoding="utf-8")
    document = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Podcast automix report</title></head><body><div id="root"></div>'
        f"<script>window.__PODCAST_REPORT__={data};</script><script>{bundle}</script>"
        "</body></html>"
    )
    destination.write_text(document, encoding="utf-8")
