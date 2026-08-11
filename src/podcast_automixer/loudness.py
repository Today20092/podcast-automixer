from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.signal import lfilter, resample_poly


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


class _StreamingMeter:
    def __init__(self, samplerate: int) -> None:
        self.samplerate = samplerate
        self.filters = []
        for stage in pyln.Meter(samplerate)._filters.values():
            state = np.zeros(max(len(stage.a), len(stage.b)) - 1)
            self.filters.append((stage.b, stage.a, state))
        self.momentary = np.empty(0, dtype=np.float64)
        self.short_term = np.empty(0, dtype=np.float64)
        self.momentary_energies: list[float] = []
        self.short_term_loudness: list[float] = []
        self.short_term_points: list[dict[str, float]] = []
        self.short_term_sample_offset = 0
        self.sample_count = 0
        self.peak_audio: list[np.ndarray] = []

    def add(self, audio: np.ndarray) -> None:
        raw = audio.astype(np.float64, copy=False)
        if not len(raw):
            return
        # Defer oversampling until result() so the FIR sees one continuous signal rather
        # than restarting at each input chunk. This is intentionally labelled estimated:
        # scipy's generic resampler is not a verified BS.1770 true-peak filter.
        self.peak_audio.append(raw.copy())
        weighted = raw
        updated = []
        for b, a, state in self.filters:
            weighted, state = lfilter(b, a, weighted, zi=state)
            updated.append((b, a, state))
        self.filters = updated
        self.momentary = np.concatenate((self.momentary, weighted))
        self.short_term = np.concatenate((self.short_term, weighted))
        self.sample_count += len(raw)
        self._consume_momentary()
        self._consume_short_term()

    def _consume_momentary(self) -> None:
        window = round(0.4 * self.samplerate)
        step = round(0.1 * self.samplerate)
        while len(self.momentary) >= window:
            self.momentary_energies.append(float(np.mean(np.square(self.momentary[:window]))))
            self.momentary = self.momentary[step:]

    def _consume_short_term(self) -> None:
        window = round(3.0 * self.samplerate)
        step = round(0.1 * self.samplerate)
        while len(self.short_term) >= window:
            energy = float(np.mean(np.square(self.short_term[:window])))
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
            self.short_term = self.short_term[step:]
            self.short_term_sample_offset += step

    def _lra_loudness(self) -> np.ndarray:
        """Return the 10 Hz short-term distribution required by EBU Tech 3342."""
        silence = np.zeros(round(1.5 * self.samplerate))
        for b, a, state in self.filters:
            silence, _ = lfilter(b, a, silence, zi=state.copy())
        remainder = np.concatenate((self.short_term, silence))
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
                self.momentary, (0, max(0, round(0.4 * self.samplerate) - len(self.momentary)))
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
        if self.peak_audio:
            oversampled = resample_poly(np.concatenate(self.peak_audio), 4, 1)
            estimated_peak = float(np.max(np.abs(oversampled)))
        else:
            estimated_peak = 0.0

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
                20.0 * math.log10(estimated_peak) if estimated_peak > 0 else None
            ),
            "short_term_timeline": [
                {**point, "lufs": finite(point["lufs"])} for point in self.short_term_points
            ],
        }


def analyze_rendered_loudness(paths: list[Path]) -> dict[str, Any]:
    """Measure each processed stem and their unattenuated virtual mono sum."""
    with sf.SoundFile(paths[0]) as first:
        samplerate = first.samplerate
    stem_meters = [_StreamingMeter(samplerate) for _ in paths]
    program_meter = _StreamingMeter(samplerate)
    sources = [sf.SoundFile(path) for path in paths]
    try:
        while True:
            chunks = [source.read(samplerate * 10, dtype="float32") for source in sources]
            if not len(chunks[0]):
                break
            for meter, chunk in zip(stem_meters, chunks, strict=True):
                meter.add(chunk)
            program_meter.add(np.sum(chunks, axis=0))
    finally:
        for source in sources:
            source.close()
    return {
        "standard": "ITU-R BS.1770 / EBU R 128",
        "stems": [meter.result() for meter in stem_meters],
        "virtual_mono_program": program_meter.result(),
    }
