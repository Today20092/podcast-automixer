from __future__ import annotations

import csv
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
from scipy.signal import resample_poly

from .loudness import KWeightFilter


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
    open_ms: float = 50.0
    close_ms: float = 500.0
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
    audio: np.ndarray,
    sr: int,
    model: Any,
    timestamp_fn: Any,
    count: int,
    trim_start: int = 0,
    trim_samples: int | None = None,
    *,
    frame_samples: int,
) -> np.ndarray:
    sidechain = resample_poly(audio, 16000, sr).astype(np.float32)
    stamps = timestamp_fn(
        sidechain,
        model,
        sampling_rate=16000,
        return_seconds=False,
        min_silence_duration_ms=100,
        speech_pad_ms=30,
    )
    mask = np.zeros(count, dtype=bool)
    trim_samples = len(audio) - trim_start if trim_samples is None else trim_samples
    for stamp in stamps:
        # Silero returns coordinates in the 16 kHz sidechain. Convert starts down
        # and ends up so resampling cannot discard any detected speech.
        relative_start = int(stamp["start"]) * sr // 16000 - trim_start
        relative_end = math.ceil(int(stamp["end"]) * sr / 16000) - trim_start
        if relative_end <= 0 or relative_start >= trim_samples:
            continue
        start = max(0, relative_start // frame_samples)
        end = min(count, math.ceil(relative_end / frame_samples))
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
    # Silero makes utterance-level decisions, so give each bounded segment context
    # on both sides and deterministically keep only the segment's central frames.
    vad_context_samples = sr

    for channel, info in enumerate(infos):
        with sf.SoundFile(info.path) as source:
            source.seek(start_frame)
            weighting = KWeightFilter(sr)
            offset = 0
            remaining = total
            while remaining:
                wanted = min(remaining, segment_samples)
                audio = source.read(wanted, dtype="float32", always_2d=False)
                if not len(audio):
                    break
                frame_offset = offset // samples_per_frame
                # Compare microphones using perceptually weighted energy while VAD remains
                # responsible for deciding whether the sound is speech-like.
                db = _frame_db(weighting.process(audio), samples_per_frame)
                end = min(analysis_frames, frame_offset + len(db))
                usable = end - frame_offset
                energies[channel, frame_offset:end] = db[:usable]
                context_start = max(start_frame, start_frame + offset - vad_context_samples)
                context_end = min(
                    start_frame + total,
                    start_frame + offset + len(audio) + vad_context_samples,
                )
                current_position = source.tell()
                source.seek(context_start)
                vad_audio = source.read(
                    context_end - context_start, dtype="float32", always_2d=False
                )
                source.seek(current_position)
                speech[channel, frame_offset:end] = _speech_mask(
                    vad_audio,
                    sr,
                    model,
                    timestamp_fn,
                    len(db),
                    start_frame + offset - context_start,
                    len(audio),
                    frame_samples=samples_per_frame,
                )[:usable]
                offset += len(audio)
                remaining -= len(audio)
                if progress:
                    progress("Analyzing", channel + 1, channel * total + offset, 3 * total)

    if np.max(energies) <= -119.0:
        raise AutomixError("All three inputs are digital silence.")

    active, calibration, floors = _classify_activity(energies, speech, settings.ambiguity_db)

    gains = make_gain_envelopes(active, settings)
    report = {
        "calibration_db": calibration.tolist(),
        "noise_floor_db": floors.tolist(),
        "active_percent": (100.0 * np.mean(active, axis=1)).tolist(),
    }
    return gains, active, report


def _classify_activity(
    energies: np.ndarray, speech: np.ndarray, ambiguity_db: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Classify ownership using calibrated levels and per-stem energetic evidence."""
    # Calibrate away stable microphone/speaker level differences without erasing local ownership.
    calibration = np.zeros(3, dtype=np.float32)
    for channel in range(3):
        candidates = energies[channel, speech[channel]]
        if len(candidates):
            calibration[channel] = np.percentile(candidates, 75)
    calibration -= np.median(calibration)
    normalized = energies - calibration[:, None]
    leader = np.max(normalized, axis=0)
    plausible = normalized >= leader[None, :] - ambiguity_db
    any_speech = np.any(speech, axis=0)
    active = plausible & (speech | any_speech[None, :])

    # Preserve energetic human sounds missed by VAD, while ignoring the estimated noise floor.
    floors = np.percentile(energies, 20, axis=1)
    normalized_floors = floors - calibration
    energetic = normalized > normalized_floors[:, None] + 12.0
    active |= plausible & energetic
    return active, calibration, floors


def make_gain_envelopes(active: np.ndarray, settings: Settings) -> np.ndarray:
    frame_ms = settings.frame_ms
    preroll = math.ceil(settings.preroll_ms / frame_ms)
    hold = math.ceil(settings.hold_ms / frame_ms)
    expanded = np.zeros_like(active)
    for channel in range(active.shape[0]):
        indices = np.flatnonzero(active[channel])
        changes = np.zeros(active.shape[1] + 1, dtype=np.int32)
        np.add.at(changes, np.maximum(0, indices - preroll), 1)
        np.add.at(changes, np.minimum(active.shape[1], indices + hold + 1), -1)
        expanded[channel] = np.cumsum(changes[:-1]) > 0

    floor_gain = 10.0 ** (settings.attenuation_db / 20.0)
    targets = np.where(expanded, 1.0, floor_gain)
    result = np.empty_like(targets, dtype=np.float32)
    open_alpha = 1.0 - math.exp(-frame_ms / settings.open_ms)
    close_alpha = 1.0 - math.exp(-frame_ms / settings.close_ms)
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
        "settings": {
            **asdict(settings),
            "opening_time_constant_ms": settings.open_ms,
            "closing_time_constant_ms": settings.close_ms,
        },
        "analysis": analysis_report,
        "gain_reduction_db": {
            "mean": (20 * np.log10(np.maximum(gains, 1e-9))).mean(axis=1).tolist(),
            "minimum": (20 * np.log10(np.maximum(gains, 1e-9))).min(axis=1).tolist(),
        },
    }
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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
