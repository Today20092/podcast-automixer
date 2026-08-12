from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
import soxr
from scipy.signal import lfilter


class KWeightFilter:
    """Stateful ITU-R BS.1770 K-weighting cascade for streamed mono audio."""

    def __init__(self, samplerate: int) -> None:
        self.filters = []
        for stage in pyln.Meter(samplerate)._filters.values():
            state = np.zeros(max(len(stage.a), len(stage.b)) - 1)
            self.filters.append((stage.b, stage.a, state))

    def process(self, audio: np.ndarray) -> np.ndarray:
        weighted = audio.astype(np.float64, copy=True)
        updated = []
        for b, a, state in self.filters:
            weighted, state = lfilter(b, a, weighted, zi=state)
            updated.append((b, a, state))
        self.filters = updated
        return weighted


def k_weight(audio: np.ndarray, samplerate: int) -> np.ndarray:
    """Apply the ITU-R BS.1770 K-weighting cascade to mono audio."""
    return KWeightFilter(samplerate).process(audio)


def _loudness(energy: float) -> float:
    return -math.inf if energy <= 0 else -0.691 + 10.0 * math.log10(energy)


class _EnergyWindows:
    """Calculate overlapping window energies with one bounded copy per input chunk."""

    def __init__(self, window: int, step: int) -> None:
        self.window = window
        self.step = step
        self.remainder = np.empty(0, dtype=np.float64)

    def add(self, audio: np.ndarray) -> np.ndarray:
        samples = np.concatenate((self.remainder, audio))
        count = max(0, (len(samples) - self.window) // self.step + 1)
        if not count:
            self.remainder = samples
            return np.empty(0, dtype=np.float64)

        starts = np.arange(count, dtype=np.int64) * self.step
        squared_prefix = np.empty(len(samples) + 1, dtype=np.float64)
        squared_prefix[0] = 0.0
        np.cumsum(np.square(samples), out=squared_prefix[1:])
        energies = (squared_prefix[starts + self.window] - squared_prefix[starts]) / self.window
        # Copy only the bounded tail so it does not retain the full chunk's allocation.
        self.remainder = samples[count * self.step :].copy()
        return energies


class _StreamingMeter:
    def __init__(self, samplerate: int) -> None:
        self.samplerate = samplerate
        self.filters = []
        for stage in pyln.Meter(samplerate)._filters.values():
            state = np.zeros(max(len(stage.a), len(stage.b)) - 1)
            self.filters.append((stage.b, stage.a, state))
        self.momentary = _EnergyWindows(round(0.4 * samplerate), round(0.1 * samplerate))
        self.short_term = _EnergyWindows(round(3.0 * samplerate), round(0.1 * samplerate))
        self.momentary_energies: list[float] = []
        self.short_term_loudness: list[float] = []
        self.short_term_points: list[dict[str, float]] = []
        self.short_term_sample_offset = 0
        self.sample_count = 0
        self.peak_resampler = soxr.ResampleStream(
            samplerate,
            samplerate * 4,
            num_channels=1,
            dtype="float32",
            quality="VHQ",
        )
        self.estimated_peak = 0.0
        self.peak_finalized = False

    def add(self, audio: np.ndarray) -> None:
        raw = audio.astype(np.float64, copy=False)
        if not len(raw):
            return
        if self.peak_finalized:
            raise RuntimeError("Cannot add audio after the loudness result is finalized.")
        oversampled = self.peak_resampler.resample_chunk(audio.astype(np.float32, copy=False))
        if len(oversampled):
            self.estimated_peak = max(
                self.estimated_peak,
                float(np.max(np.abs(oversampled))),
            )
        weighted = raw
        updated = []
        for b, a, state in self.filters:
            weighted, state = lfilter(b, a, weighted, zi=state)
            updated.append((b, a, state))
        self.filters = updated
        self.sample_count += len(raw)
        self.momentary_energies.extend(self.momentary.add(weighted))
        for energy in self.short_term.add(weighted):
            loudness = _loudness(energy)
            self.short_term_loudness.append(loudness)
            # The LRA calculation needs the full 10 Hz distribution, but the report
            # timeline remains at 1 Hz so long recordings do not produce huge payloads.
            if (len(self.short_term_loudness) - 1) % 10 == 0:
                self.short_term_points.append(
                    {
                        "seconds": self.short_term_sample_offset / self.samplerate,
                        "lufs": loudness,
                    }
                )
            self.short_term_sample_offset += self.short_term.step

    def _lra_loudness(self) -> np.ndarray:
        """Return the 10 Hz short-term distribution required by EBU Tech 3342."""
        silence = np.zeros(round(1.5 * self.samplerate))
        for b, a, state in self.filters:
            silence, _ = lfilter(b, a, silence, zi=state.copy())
        remainder = np.concatenate((self.short_term.remainder, silence))
        values = list(self.short_term_loudness)
        window = round(3.0 * self.samplerate)
        step = round(0.1 * self.samplerate)
        while len(remainder) >= window:
            values.append(_loudness(float(np.mean(np.square(remainder[:window])))))
            remainder = remainder[step:]
        return np.array(values)

    def result(self) -> dict[str, Any]:
        if not self.momentary_energies and self.sample_count:
            padded = np.pad(
                self.momentary.remainder,
                (
                    0,
                    max(
                        0,
                        round(0.4 * self.samplerate) - len(self.momentary.remainder),
                    ),
                ),
            )
            self.momentary_energies.append(float(np.mean(np.square(padded))))
        loudness = np.array([_loudness(value) for value in self.momentary_energies])
        absolute = np.array(self.momentary_energies)[loudness >= -70.0]
        if len(absolute):
            relative_gate = _loudness(float(np.mean(absolute))) - 10.0
            gated = np.array(self.momentary_energies)[
                (loudness >= -70.0) & (loudness > relative_gate)
            ]
            integrated = _loudness(float(np.mean(gated)))
        else:
            integrated = -math.inf

        short_values = self._lra_loudness()
        short_absolute = short_values[np.isfinite(short_values) & (short_values >= -70.0)]
        measured_short = np.array(self.short_term_loudness)
        measured_short = measured_short[np.isfinite(measured_short)]
        if len(short_absolute):
            short_power = np.power(10.0, (short_absolute + 0.691) / 10.0)
            relative = _loudness(float(np.mean(short_power))) - 20.0
            distribution = short_absolute[short_absolute >= relative]
            lra = float(np.percentile(distribution, 95) - np.percentile(distribution, 10))
        else:
            lra = 0.0
        finite_momentary = loudness[np.isfinite(loudness)]
        if not self.peak_finalized:
            oversampled = self.peak_resampler.resample_chunk(
                np.empty(0, dtype=np.float32), last=True
            )
            if len(oversampled):
                self.estimated_peak = max(
                    self.estimated_peak,
                    float(np.max(np.abs(oversampled))),
                )
            self.peak_finalized = True

        def finite(value: float) -> float | None:
            return value if math.isfinite(value) else None

        return {
            "integrated_lufs": finite(integrated),
            "maximum_momentary_lufs": (
                float(np.max(finite_momentary)) if len(finite_momentary) else None
            ),
            "maximum_short_term_lufs": (
                float(np.max(measured_short)) if len(measured_short) else None
            ),
            "loudness_range_lu": lra,
            "maximum_estimated_true_peak_dbtp": (
                20.0 * math.log10(self.estimated_peak) if self.estimated_peak > 0 else None
            ),
            "short_term_timeline": [
                {**point, "lufs": finite(point["lufs"])} for point in self.short_term_points
            ],
        }


LoudnessProgress = Callable[[str, int, int, int], None]


def analyze_rendered_loudness(
    paths: list[Path], progress: LoudnessProgress | None = None
) -> dict[str, Any]:
    """Measure each processed stem and their unattenuated virtual mono sum."""
    with sf.SoundFile(paths[0]) as first:
        samplerate = first.samplerate
        total = first.frames
    stem_meters = [_StreamingMeter(samplerate) for _ in paths]
    program_meter = _StreamingMeter(samplerate)
    sources = [sf.SoundFile(path) for path in paths]
    chunk_size = samplerate * 10
    total_steps = math.ceil(total / chunk_size) + len(stem_meters) + 1
    completed_steps = 0
    try:
        if progress:
            progress("Measuring loudness", len(paths), 0, total_steps)
        while True:
            chunks = [source.read(chunk_size, dtype="float32") for source in sources]
            if not len(chunks[0]):
                break
            for meter, chunk in zip(stem_meters, chunks, strict=True):
                meter.add(chunk)
            program_meter.add(np.sum(chunks, axis=0))
            completed_steps += 1
            if progress:
                progress("Measuring loudness", len(paths), completed_steps, total_steps)
    finally:
        for source in sources:
            source.close()
    stem_results = []
    for meter in stem_meters:
        stem_results.append(meter.result())
        completed_steps += 1
        if progress:
            progress("Measuring loudness", len(paths), completed_steps, total_steps)
    program_result = program_meter.result()
    completed_steps += 1
    if progress:
        progress("Measuring loudness", len(paths), completed_steps, total_steps)
    return {
        "standard": "ITU-R BS.1770 / EBU R 128",
        "stems": stem_results,
        "virtual_mono_program": program_result,
    }
