from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .core import AudioInfo, Settings

TRACK_COLORS = (
    "#3b82f6", "#f59e0b", "#10b981", "#ef4444",
    "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16",
)


@dataclass(frozen=True)
class Report:
    """Facts and derived insights for every report format.

    Array values are linear gain and frame ownership. Serialized units and nullability
    are defined by the payload methods below.
    """

    infos: list[AudioInfo]
    settings: Settings
    gains: np.ndarray
    active: np.ndarray
    analysis: dict[str, Any]

    @property
    def gain_db(self) -> np.ndarray:
        """Applied gain in decibels, floored to avoid negative infinity."""
        return 20.0 * np.log10(np.maximum(self.gains, 1e-9))

    def json_payload(self) -> dict[str, Any]:
        return {
            "version": 1,
            "inputs": [{**asdict(info), "path": str(info.path)} for info in self.infos],
            "settings": {
                **asdict(self.settings),
                "opening_time_constant_ms": self.settings.open_ms,
                "closing_time_constant_ms": self.settings.close_ms,
            },
            "analysis": self.analysis,
            "gain_reduction_db": {
                "mean": self.gain_db.mean(axis=1).tolist(),
                "minimum": self.gain_db.min(axis=1).tolist(),
            },
        }

    def html_payload(self) -> dict[str, Any]:
        return {
            "attenuationDb": self.settings.attenuation_db,
            "openingTimeConstantMs": self.settings.open_ms,
            "closingTimeConstantMs": self.settings.close_ms,
            "loudness": self.analysis.get("loudness"),
            **build_report_insights(self.active, self.gain_db, self.settings.frame_ms),
            "tracks": [
                {
                    "id": f"track-{index + 1}",
                    "name": info.path.stem,
                    "active": float(self.analysis["active_percent"][index]),
                    "meanGain": float(self.gain_db[index].mean()),
                    "calibration": float(self.analysis["calibration_db"][index]),
                    "noiseFloor": float(self.analysis["noise_floor_db"][index]),
                    "minimumGain": float(self.gain_db[index].min()),
                    "color": TRACK_COLORS[index % len(TRACK_COLORS)],
                }
                for index, info in enumerate(self.infos)
            ],
        }

    def diagnostics_rows(self) -> Iterator[list[str | int]]:
        gain_db = self.gain_db
        track_count = self.active.shape[0]
        for index in range(self.active.shape[1]):
            yield [
                f"{index * self.settings.frame_ms / 1000:.3f}",
                *(int(self.active[channel, index]) for channel in range(track_count)),
                *(f"{gain_db[channel, index]:.3f}" for channel in range(track_count)),
            ]


def build_report_insights(active: np.ndarray, gain_db: np.ndarray, frame_ms: int) -> dict[str, Any]:
    """Summarize frame decisions into episode-scale, display-ready diagnostics."""
    track_count = active.shape[0]
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

    timeline = []
    for start in range(0, frame_count, window_frames):
        stop = min(start + window_frames, frame_count)
        timeline.append(
            {
                "start_seconds": round(start * frame_seconds, 3),
                "end_seconds": round(stop * frame_seconds, 3),
                "gain_db": [
                    round(float(gain_db[channel, start:stop].mean()), 3)
                    for channel in range(track_count)
                ],
                "attenuated_percent": [
                    round(float(np.mean(gain_db[channel, start:stop] < -0.5) * 100), 1)
                    for channel in range(track_count)
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
                    for channel in range(track_count)
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
        for channel in range(track_count)
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
                        channel
                        for channel in range(track_count)
                        if bool(np.any(active[channel, start:stop]))
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


def write_json_report(destination: Path, report: Report) -> None:
    destination.write_text(json.dumps(report.json_payload(), indent=2), encoding="utf-8")


def write_diagnostics(destination: Path, report: Report) -> None:
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        track_count = report.active.shape[0]
        writer.writerow(
            [
                "time_seconds",
                *(f"a{channel + 1:02}_active" for channel in range(track_count)),
                *(f"a{channel + 1:02}_gain_db" for channel in range(track_count)),
            ]
        )
        writer.writerows(report.diagnostics_rows())


def write_html_report(destination: Path, report: Report) -> None:
    """Write the interactive report as one self-contained HTML file."""
    bundle_path = Path(__file__).with_name("report.bundle.js")
    if not bundle_path.exists():
        raise RuntimeError("The packaged HTML report bundle is missing.")

    data = json.dumps(report.html_payload(), separators=(",", ":")).replace("<", "\\u003c")
    bundle = bundle_path.read_text(encoding="utf-8")
    document = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Podcast automix report</title></head><body><div id="root"></div>'
        f"<script>window.__PODCAST_REPORT__={data};</script><script>{bundle}</script>"
        "</body></html>"
    )
    destination.write_text(document, encoding="utf-8")
