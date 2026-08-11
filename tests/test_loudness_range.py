import numpy as np
import pyloudnorm as pyln
import pytest

from podcast_automixer.loudness import _StreamingMeter

SAMPLE_RATE = 8000


def _tone(duration: float, amplitude: float = 0.1) -> np.ndarray:
    time = np.arange(round(duration * SAMPLE_RATE)) / SAMPLE_RATE
    return amplitude * np.sin(2.0 * np.pi * 440.0 * time)


def _measure(audio: np.ndarray) -> tuple[float, _StreamingMeter]:
    meter = _StreamingMeter(SAMPLE_RATE)
    for chunk in np.array_split(audio, 7):
        meter.add(chunk)
    return meter.result()["loudness_range_lu"], meter


@pytest.mark.parametrize(
    "audio",
    [
        _tone(30.0),
        np.concatenate((_tone(10.0, 0.01), _tone(10.0), _tone(10.0, 0.03))),
        _tone(30.0) * np.tile(np.linspace(0.1, 1.0, SAMPLE_RATE // 2), 60),
        _tone(2.0),
    ],
    ids=["stationary", "stepped", "rapidly-varying", "short"],
)
def test_loudness_range_matches_pyloudnorm(audio: np.ndarray) -> None:
    actual, _ = _measure(audio)

    assert actual == pytest.approx(pyln.Meter(SAMPLE_RATE).loudness_range(audio), abs=0.1)


def test_silent_loudness_range_has_no_distribution() -> None:
    audio = np.zeros(SAMPLE_RATE * 5)

    actual, _ = _measure(audio)

    assert np.isnan(pyln.Meter(SAMPLE_RATE).loudness_range(audio))
    assert actual == 0.0


def test_lra_uses_10_hz_samples_but_report_timeline_stays_at_1_hz() -> None:
    _, meter = _measure(_tone(30.0))

    assert len(meter.short_term_loudness) == 271
    assert len(meter.short_term_points) == 28
    assert [point["seconds"] for point in meter.short_term_points[:3]] == [0.0, 1.0, 2.0]
