from __future__ import annotations

import csv
import html
import json
import math
import os
import struct
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from scipy.ndimage import maximum_filter1d
from scipy.signal import resample_poly


class AutomixError(RuntimeError):
    """A user-actionable automixing failure."""


ProgressCallback = Callable[[str, int, int, int], None]


@dataclass(frozen=True)
class Settings:
    attenuation_db: float = -6.0
    frame_ms: int = 20
    ambiguity_db: float = 9.0
    preroll_ms: int = 150
    hold_ms: int = 400
    open_ms: int = 50
    close_ms: int = 500
    segment_seconds: int = 30


@dataclass(frozen=True)
class AudioInfo:
    path: Path
    samplerate: int
    channels: int
    frames: int
    subtype: str
    format: str


def inspect_inputs(paths: list[Path]) -> list[AudioInfo]:
    if len(paths) != 3:
        raise AutomixError("Exactly three WAV files are required.")
    infos: list[AudioInfo] = []
    for path in paths:
        if not path.is_file():
            raise AutomixError(f"File not found: {path}")
        raw = sf.info(path)
        if raw.format not in {"WAV", "WAVEX", "RF64"}:
            raise AutomixError(f"Not a WAV-family file: {path}")
        if raw.channels != 1:
            raise AutomixError(f"Version 1 requires mono stems: {path}")
        infos.append(
            AudioInfo(path, raw.samplerate, raw.channels, raw.frames, raw.subtype, raw.format)
        )
    expected = infos[0]
    for info in infos[1:]:
        fields = (info.samplerate, info.channels, info.frames, info.subtype)
        wanted = (expected.samplerate, expected.channels, expected.frames, expected.subtype)
        if fields != wanted:
            raise AutomixError(
                "Inputs must have identical sample rate, channels, frame count, and subtype."
            )
    return infos


def _load_vad() -> tuple[Any, Any]:
    try:
        from silero_vad import get_speech_timestamps, load_silero_vad

        return load_silero_vad(), get_speech_timestamps
    except Exception as exc:  # pragma: no cover - environment/model failures vary
        raise AutomixError(f"Could not load the pinned Silero VAD model: {exc}") from exc


def _frame_db(audio: np.ndarray, frame_samples: int) -> np.ndarray:
    count = math.ceil(len(audio) / frame_samples)
    padded = np.pad(audio, (0, count * frame_samples - len(audio)))
    frames = padded.reshape(count, frame_samples).astype(np.float64)
    power = np.mean(frames * frames, axis=1)
    return 10.0 * np.log10(np.maximum(power, 1e-12))


def _speech_mask(
    audio: np.ndarray, sr: int, model: Any, timestamp_fn: Any, count: int
) -> np.ndarray:
    sidechain = resample_poly(audio, 16000, sr).astype(np.float32)
    stamps = timestamp_fn(sidechain, model, sampling_rate=16000, return_seconds=True)
    mask = np.zeros(count, dtype=bool)
    frame_seconds = len(audio) / sr / max(count, 1)
    for stamp in stamps:
        start = max(0, int(float(stamp["start"]) / frame_seconds))
        end = min(count, math.ceil(float(stamp["end"]) / frame_seconds))
        mask[start:end] = True
    return mask


def analyze(
    infos: list[AudioInfo],
    settings: Settings,
    start_frame: int = 0,
    frame_count: int | None = None,
    progress: ProgressCallback | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    sr = infos[0].samplerate
    total = frame_count if frame_count is not None else infos[0].frames - start_frame
    samples_per_frame = round(sr * settings.frame_ms / 1000)
    analysis_frames = math.ceil(total / samples_per_frame)
    energies = np.full((3, analysis_frames), -120.0, dtype=np.float32)
    speech = np.zeros((3, analysis_frames), dtype=bool)
    model, timestamp_fn = _load_vad()
    segment_samples = settings.segment_seconds * sr

    for channel, info in enumerate(infos):
        with sf.SoundFile(info.path) as source:
            source.seek(start_frame)
            offset = 0
            remaining = total
            while remaining:
                wanted = min(remaining, segment_samples)
                audio = source.read(wanted, dtype="float32", always_2d=False)
                if not len(audio):
                    break
                frame_offset = offset // samples_per_frame
                db = _frame_db(audio, samples_per_frame)
                end = min(analysis_frames, frame_offset + len(db))
                usable = end - frame_offset
                energies[channel, frame_offset:end] = db[:usable]
                speech[channel, frame_offset:end] = _speech_mask(
                    audio, sr, model, timestamp_fn, len(db)
                )[:usable]
                offset += len(audio)
                remaining -= len(audio)
                if progress:
                    progress("Analyzing", channel + 1, channel * total + offset, 3 * total)

    if np.max(energies) <= -119.0:
        raise AutomixError("All three inputs are digital silence.")

    # Calibrate away stable microphone/speaker level differences without erasing local ownership.
    calibration = np.zeros(3, dtype=np.float32)
    for channel in range(3):
        candidates = energies[channel, speech[channel]]
        if len(candidates):
            calibration[channel] = np.percentile(candidates, 75)
    calibration -= np.median(calibration)
    normalized = energies - calibration[:, None]
    leader = np.max(normalized, axis=0)
    plausible = normalized >= leader[None, :] - settings.ambiguity_db
    any_speech = np.any(speech, axis=0)
    active = plausible & (speech | any_speech[None, :])

    # Preserve energetic human sounds missed by VAD, while ignoring the estimated noise floor.
    floors = np.percentile(energies, 20, axis=1)
    energetic = leader > np.max(floors + 12.0)
    active |= plausible & energetic[None, :]

    gains = make_gain_envelopes(active, settings)
    report = {
        "calibration_db": calibration.tolist(),
        "noise_floor_db": floors.tolist(),
        "active_percent": (100.0 * np.mean(active, axis=1)).tolist(),
    }
    return gains, active, report


def make_gain_envelopes(active: np.ndarray, settings: Settings) -> np.ndarray:
    frame_ms = settings.frame_ms
    preroll = math.ceil(settings.preroll_ms / frame_ms)
    hold = math.ceil(settings.hold_ms / frame_ms)
    expanded = np.zeros_like(active)
    for channel in range(active.shape[0]):
        held = maximum_filter1d(
            active[channel].astype(np.uint8), size=hold + 1, origin=-(hold // 2)
        )
        indices = np.flatnonzero(held)
        expanded[channel, np.maximum(0, indices - preroll)] = True
        expanded[channel] |= held.astype(bool)

    floor_gain = 10.0 ** (settings.attenuation_db / 20.0)
    targets = np.where(expanded, 1.0, floor_gain)
    result = np.empty_like(targets, dtype=np.float32)
    open_alpha = min(1.0, frame_ms / settings.open_ms)
    close_alpha = min(1.0, frame_ms / settings.close_ms)
    for channel in range(3):
        value = float(targets[channel, 0])
        for index, target in enumerate(targets[channel]):
            alpha = open_alpha if target > value else close_alpha
            value += alpha * (float(target) - value)
            result[channel, index] = value
    return result


def output_path(path: Path, preview: bool) -> Path:
    suffix = "_auto-mixed-preview.wav" if preview else "_auto-mixed.wav"
    return path.with_name(f"{path.stem}{suffix}")


def _read_riff_chunk(path: Path, wanted: bytes) -> bytes | None:
    with path.open("rb") as stream:
        if stream.read(4) not in {b"RIFF", b"RF64"}:
            return None
        stream.seek(12)
        while header := stream.read(8):
            chunk_id, size = struct.unpack("<4sI", header)
            payload = stream.read(size)
            if chunk_id == wanted:
                return payload
            if size % 2:
                stream.seek(1, os.SEEK_CUR)
    return None


def _inject_bext(source: Path, destination: Path, sample_offset: int) -> None:
    bext = _read_riff_chunk(source, b"bext")
    if bext is None:
        return
    if len(bext) >= 346:
        mutable = bytearray(bext)
        original_reference = struct.unpack_from("<Q", mutable, 338)[0]
        struct.pack_into("<Q", mutable, 338, original_reference + sample_offset)
        bext = bytes(mutable)
    temporary = destination.with_suffix(".bwf-tmp.wav")
    with destination.open("rb") as incoming, temporary.open("wb") as outgoing:
        header = incoming.read(12)
        outgoing.write(header)
        inserted = False
        while chunk_header := incoming.read(8):
            chunk_id, size = struct.unpack("<4sI", chunk_header)
            if chunk_id == b"bext":
                incoming.seek(size + size % 2, os.SEEK_CUR)
                continue
            if chunk_id == b"data" and not inserted:
                outgoing.write(struct.pack("<4sI", b"bext", len(bext)))
                outgoing.write(bext)
                if len(bext) % 2:
                    outgoing.write(b"\0")
                inserted = True
            outgoing.write(chunk_header)
            remaining = size + size % 2
            while remaining:
                block = incoming.read(min(1024 * 1024, remaining))
                if not block:
                    raise AutomixError(f"Unexpected end of WAV file: {destination}")
                outgoing.write(block)
                remaining -= len(block)
        file_size = outgoing.tell()
        outgoing.seek(4)
        outgoing.write(struct.pack("<I", file_size - 8))
    temporary.replace(destination)


def render(
    infos: list[AudioInfo],
    gains: np.ndarray,
    settings: Settings,
    start_frame: int,
    frame_count: int,
    preview: bool,
    overwrite: bool,
    progress: ProgressCallback | None = None,
) -> list[Path]:
    outputs = [output_path(info.path, preview) for info in infos]
    collisions = [path for path in outputs if path.exists()]
    if collisions and not overwrite:
        raise AutomixError(f"Output already exists: {collisions[0]}")
    sr = infos[0].samplerate
    samples_per_frame = round(sr * settings.frame_ms / 1000)
    chunk = sr * 30
    for channel, (info, destination) in enumerate(zip(infos, outputs, strict=True)):
        with (
            sf.SoundFile(info.path) as source,
            sf.SoundFile(
                destination,
                mode="w",
                samplerate=sr,
                channels=1,
                format=info.format,
                subtype=info.subtype,
            ) as target,
        ):
            source.seek(start_frame)
            offset = 0
            remaining = frame_count
            while remaining:
                wanted = min(remaining, chunk)
                audio = source.read(wanted, dtype="float32", always_2d=False)
                sample_positions = (offset + np.arange(len(audio))) / samples_per_frame
                frame_positions = np.arange(gains.shape[1])
                gain = np.interp(sample_positions, frame_positions, gains[channel])
                target.write((audio * gain).astype(np.float32))
                offset += len(audio)
                remaining -= len(audio)
                if progress:
                    progress(
                        "Rendering", channel + 1, channel * frame_count + offset, 3 * frame_count
                    )
        _inject_bext(info.path, destination, start_frame)
    return outputs


def write_report(
    destination: Path,
    infos: list[AudioInfo],
    settings: Settings,
    gains: np.ndarray,
    analysis_report: dict[str, Any],
) -> None:
    payload = {
        "version": 1,
        "inputs": [{**asdict(info), "path": str(info.path)} for info in infos],
        "settings": asdict(settings),
        "analysis": analysis_report,
        "gain_reduction_db": {
            "mean": (20 * np.log10(np.maximum(gains, 1e-9))).mean(axis=1).tolist(),
            "minimum": (20 * np.log10(np.maximum(gains, 1e-9))).min(axis=1).tolist(),
        },
    }
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_html_report(
    destination: Path,
    infos: list[AudioInfo],
    settings: Settings,
    gains: np.ndarray,
    analysis_report: dict[str, Any],
) -> None:
    """Write a portable visual summary with no external runtime dependencies."""
    gain_db = 20 * np.log10(np.maximum(gains, 1e-9))
    tracks = [
        {
            "name": info.path.stem,
            "active": float(analysis_report["active_percent"][index]),
            "mean_gain": float(gain_db[index].mean()),
            "calibration": float(analysis_report["calibration_db"][index]),
            "noise_floor": float(analysis_report["noise_floor_db"][index]),
            "minimum_gain": float(gain_db[index].min()),
        }
        for index, info in enumerate(infos)
    ]

    def chart(title: str, key: str, unit: str, lower: float, upper: float) -> str:
        span = upper - lower
        bars = []
        for index, track in enumerate(tracks):
            value = track[key]
            start = min(0.0, value)
            width = abs(value) / span * 100
            left = (start - lower) / span * 100
            label = html.escape(track["name"])
            details = html.escape(
                f'{track["name"]}: {value:.2f}{unit}; noise floor '
                f'{track["noise_floor"]:.2f} dB; minimum gain '
                f'{track["minimum_gain"]:.2f} dB'
            )
            bars.append(
                f'<li tabindex="0" aria-label="{details}">'
                f'<span class="track">{label}</span>'
                '<span class="plot">'
                f'<span class="bar track-{index + 1}" style="left:{left:.3f}%;width:{width:.3f}%"></span>'
                f'<span class="value" style="left:{max(2.0, min(94.0, (value - lower) / span * 100)):.3f}%">'
                f'{value:.2f}{unit}</span></span></li>'
            )
        return (
            f'<section class="chart" aria-labelledby="{key}-title">'
            f'<h2 id="{key}-title">{html.escape(title)}</h2>'
            f'<div class="scale"><span>{lower:g}{unit}</span><span>0{unit}</span>'
            f'<span>{upper:g}{unit}</span></div><ol>{"".join(bars)}</ol></section>'
        )

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Podcast automix report</title>
<style>
:root {{ color-scheme: light dark; --bg:#f7f7f5; --fg:#20201e; --muted:#6a6a64;
  --grid:#d7d7d1; --one:#2563eb; --two:#d97706; --three:#059669; }}
@media (prefers-color-scheme:dark) {{ :root {{ --bg:#171716; --fg:#ededeb; --muted:#aaa9a2;
  --grid:#41413d; --one:#60a5fa; --two:#fbbf24; --three:#34d399; }} }}
* {{ box-sizing:border-box }} body {{ margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.45 system-ui,sans-serif }} main {{ width:min(960px,100%); margin:auto; padding:32px 20px 48px }}
h1 {{ margin:0 0 4px; font-size:clamp(1.65rem,4vw,2.35rem) }} .subtitle {{ color:var(--muted); margin:0 0 32px }}
.chart {{ margin:0 0 38px }} h2 {{ font-size:1.05rem; margin:0 0 8px }}
.scale {{ display:flex; justify-content:space-between; margin-left:min(38%,260px); color:var(--muted); font-size:.78rem }}
ol {{ list-style:none; margin:0; padding:0 }} li {{ display:grid; grid-template-columns:minmax(120px,260px) 1fr;
  gap:14px; align-items:center; min-height:48px; border-top:1px solid var(--grid); outline-offset:3px }}
.track {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap }} .plot {{ position:relative; height:26px;
  background:linear-gradient(to right,transparent 49.8%,var(--grid) 50%,transparent 50.2%) }}
.bar {{ position:absolute; top:5px; height:16px; border-radius:2px; min-width:2px }}
.track-1 {{ background:var(--one) }} .track-2 {{ background:var(--two) }} .track-3 {{ background:var(--three) }}
.value {{ position:absolute; top:3px; transform:translateX(-50%); font-size:.8rem; font-variant-numeric:tabular-nums;
  background:var(--bg); padding:1px 3px }}
.legend {{ display:flex; flex-wrap:wrap; gap:16px; color:var(--muted); font-size:.85rem; margin-top:-18px }}
.legend span::before {{ content:""; display:inline-block; width:10px; height:10px; margin-right:6px; background:var(--swatch) }}
@media(max-width:560px) {{ main {{ padding-inline:14px }} li {{ grid-template-columns:1fr; gap:3px; padding:8px 0 }}
  .scale {{ margin-left:0 }} }}
</style>
</head>
<body><main>
<h1>Podcast automix report</h1>
<p class="subtitle">Three synchronized microphone tracks · inactive attenuation {settings.attenuation_db:g} dB</p>
{chart("Active time", "active", "%", 0, 100)}
{chart("Mean gain reduction", "mean_gain", " dB", settings.attenuation_db, 0)}
{chart("Calibration adjustment", "calibration", " dB", -12, 12)}
<div class="legend" aria-label="Track colors">
{''.join(f'<span style="--swatch:var(--{name})">{html.escape(track["name"])}</span>' for name, track in zip(("one", "two", "three"), tracks, strict=True))}
</div>
</main></body></html>"""
    destination.write_text(document, encoding="utf-8")


def write_diagnostics(
    destination: Path, active: np.ndarray, gains: np.ndarray, frame_ms: int
) -> None:
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "time_seconds",
                "a01_active",
                "a02_active",
                "a03_active",
                "a01_gain_db",
                "a02_gain_db",
                "a03_gain_db",
            ]
        )
        gain_db = 20.0 * np.log10(np.maximum(gains, 1e-9))
        for index in range(active.shape[1]):
            writer.writerow(
                [
                    f"{index * frame_ms / 1000:.3f}",
                    *(int(active[channel, index]) for channel in range(3)),
                    *(f"{gain_db[channel, index]:.3f}" for channel in range(3)),
                ]
            )
