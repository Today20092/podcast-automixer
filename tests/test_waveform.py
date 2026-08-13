from json import dumps
from pathlib import Path
from time import monotonic, sleep

import numpy as np
import pytest
import soundfile as sf

import podcast_automixer.desktop as desktop
from podcast_automixer.desktop import DesktopBridge
from podcast_automixer.waveform import WAVEFORM_POINT_LIMIT, analyze_monitoring_waveform


def write(path: Path, samples: np.ndarray, samplerate: int = 8_000) -> Path:
    sf.write(path, samples.astype(np.float32), samplerate, subtype="FLOAT")
    return path


def test_silence_has_a_real_flat_envelope(tmp_path: Path) -> None:
    result = analyze_monitoring_waveform([write(tmp_path / "silence.wav", np.zeros(8_000))], 8)

    assert result["program"] == "original_monitoring_mix"
    assert result["duration_seconds"] == 1.0
    assert result["points"] == [[0.0, 0.0]] * 8


def test_impulses_land_in_their_deterministic_time_bins(tmp_path: Path) -> None:
    samples = np.zeros(8_000)
    samples[1_000] = 0.75
    samples[6_000] = -0.5

    points = analyze_monitoring_waveform([write(tmp_path / "impulses.wav", samples)], 8)["points"]

    assert points[1] == [0.0, 0.75]
    assert points[6] == [-0.5, 0.0]
    assert points[0] == [0.0, 0.0]


def test_constant_tone_preserves_visible_peaks_and_monitoring_sum(tmp_path: Path) -> None:
    time = np.arange(8_000) / 8_000
    tone = np.sin(2 * np.pi * 100 * time).astype(np.float32) * 0.25
    paths = [write(tmp_path / f"tone-{index}.wav", tone) for index in range(2)]

    points = np.asarray(analyze_monitoring_waveform(paths, 16)["points"])

    assert np.all(points[:, 0] == pytest.approx(-0.5, abs=0.001))
    assert np.all(points[:, 1] == pytest.approx(0.5, abs=0.001))


def test_long_input_has_bounded_payload_and_chunk_memory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = write(tmp_path / "long.wav", np.linspace(-0.25, 0.25, 800_000))
    read_sizes: list[int] = []
    original = sf.SoundFile.read

    def tracked_read(self, frames=-1, *args, **kwargs):
        read_sizes.append(frames)
        return original(self, frames, *args, **kwargs)

    monkeypatch.setattr(sf.SoundFile, "read", tracked_read)
    result = analyze_monitoring_waveform([path])

    assert len(result["points"]) == WAVEFORM_POINT_LIMIT
    assert max(read_sizes) == 65_536
    assert result["points"][0][0] == pytest.approx(-0.25, abs=0.001)
    assert result["points"][-1][1] == pytest.approx(0.25, abs=0.001)


def test_bridge_returns_only_the_bounded_original_monitoring_mix(tmp_path: Path) -> None:
    samples = np.zeros(8_000, dtype=np.float32)
    paths = [write(tmp_path / f"voice-{index}.wav", samples) for index in range(2)]

    bridge = DesktopBridge()
    started = monotonic()
    assert bridge.start_waveform_overview([str(path) for path in paths]) == {"state": "loading"}
    assert monotonic() - started < 0.1
    while (status := bridge.waveform_overview_status())["state"] == "loading":
        sleep(0.01)
    result = status["result"]

    assert set(result) == {"program", "duration_seconds", "points"}
    assert result["program"] == "original_monitoring_mix"
    assert len(result["points"]) <= WAVEFORM_POINT_LIMIT
    assert len(dumps(result).encode()) < 16_000


def test_renderer_uses_real_points_and_one_full_duration_time_axis() -> None:
    renderer = (Path(desktop.__file__).parent / "comparison_playback.js").read_text(
        encoding="utf-8"
    )

    assert "start_waveform_overview(paths)" in renderer
    assert "waveform_overview_status()" in renderer
    assert "overview.points.map" in renderer
    assert "Loading Original Monitoring Mix waveform" in renderer
    assert "Waveform unavailable" in renderer
    assert "overviewPromise?.key === key" in renderer
    assert "startSeconds + current" in renderer
    assert "duration / fullDuration" in renderer
    assert "prefers-reduced-motion:reduce" in renderer
    assert "aria-valuetext" in renderer


def test_preview_selection_and_playhead_use_the_full_recording_axis() -> None:
    full_duration, start, preview_duration, playhead = 100.0, 20.0, 30.0, 5.0

    assert start / full_duration * 100 == 20.0
    assert preview_duration / full_duration * 100 == 30.0
    assert (start + playhead) / full_duration * 100 == 25.0
