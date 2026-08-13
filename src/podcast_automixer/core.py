from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
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


@dataclass(frozen=True)
class AnalysisResult:
    """Complete ownership decision and its frame/sample coordinate system."""

    gains: np.ndarray
    active: np.ndarray
    calibration_db: np.ndarray
    noise_floor_db: np.ndarray
    frame_ms: int
    start_sample: int
    sample_count: int
    samples_per_frame: int

    @property
    def report_values(self) -> dict[str, Any]:
        """Return the stable, JSON-ready analysis values used by reports."""
        return {
            "calibration_db": self.calibration_db.tolist(),
            "noise_floor_db": self.noise_floor_db.tolist(),
            "active_percent": (100.0 * np.mean(self.active, axis=1)).tolist(),
        }


def inspect_inputs(paths: list[Path]) -> list[AudioInfo]:
    if not paths:
        raise AutomixError("At least one WAV file is required.")
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
) -> AnalysisResult:
    sr = infos[0].samplerate
    total = frame_count if frame_count is not None else infos[0].frames - start_frame
    samples_per_frame = round(sr * settings.frame_ms / 1000)
    analysis_frames = math.ceil(total / samples_per_frame)
    track_count = len(infos)
    energies = np.full((track_count, analysis_frames), -120.0, dtype=np.float32)
    speech = np.zeros((track_count, analysis_frames), dtype=bool)
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
                    progress("Analyzing", channel + 1, channel * total + offset, len(infos) * total)

    if np.max(energies) <= -119.0:
        raise AutomixError("All inputs are digital silence.")

    active, calibration, floors = _classify_activity(energies, speech, settings.ambiguity_db)

    if progress:
        progress("Calculating gain automation", 1, 1, 1)
    gains = make_gain_envelopes(active, settings)
    return AnalysisResult(
        gains=gains,
        active=active,
        calibration_db=calibration,
        noise_floor_db=floors,
        frame_ms=settings.frame_ms,
        start_sample=start_frame,
        sample_count=total,
        samples_per_frame=samples_per_frame,
    )


def _classify_activity(
    energies: np.ndarray, speech: np.ndarray, ambiguity_db: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Classify ownership using calibrated levels and per-stem energetic evidence."""
    # Calibrate away stable microphone/speaker level differences without erasing local ownership.
    calibration = np.zeros(energies.shape[0], dtype=np.float32)
    for channel in range(energies.shape[0]):
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
    for channel in range(active.shape[0]):
        value = float(targets[channel, 0])
        for index, target in enumerate(targets[channel]):
            alpha = open_alpha if target > value else close_alpha
            value += alpha * (float(target) - value)
            result[channel, index] = value
    return result
