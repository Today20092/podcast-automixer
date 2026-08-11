import struct
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from podcast_automixer.cli import parse_dropped_paths
from podcast_automixer.core import (
    AutomixError,
    Settings,
    _classify_activity,
    _inject_bext,
    _read_riff_chunk,
    _speech_mask,
    inspect_inputs,
    make_gain_envelopes,
    write_diagnostics,
)
from podcast_automixer.loudness import analyze_rendered_loudness, k_weight
from podcast_automixer.report import build_report_insights, write_html_report


def test_k_weighting_favors_voice_band_over_low_frequency_rumble() -> None:
    samplerate = 48000
    seconds = np.arange(samplerate, dtype=np.float64) / samplerate
    voice_band = np.sin(2 * np.pi * 1000 * seconds)
    rumble = np.sin(2 * np.pi * 30 * seconds)

    voice_rms = np.sqrt(np.mean(np.square(k_weight(voice_band, samplerate))))
    rumble_rms = np.sqrt(np.mean(np.square(k_weight(rumble, samplerate))))

    assert voice_rms > rumble_rms * 2


def test_loudness_report_measures_stems_virtual_program_and_timeline(tmp_path: Path) -> None:
    samplerate = 48000
    seconds = np.arange(samplerate * 4, dtype=np.float64) / samplerate
    tone = (0.1 * np.sin(2 * np.pi * 1000 * seconds)).astype(np.float32)
    paths = []
    for index in range(3):
        path = tmp_path / f"stem-{index}.wav"
        sf.write(path, tone, samplerate, subtype="FLOAT")
        paths.append(path)

    report = analyze_rendered_loudness(paths)

    stem = report["stems"][0]
    program = report["virtual_mono_program"]
    assert report["standard"] == "ITU-R BS.1770 / EBU R 128"
    assert stem["integrated_lufs"] == pytest.approx(-23.05, abs=0.25)
    assert program["integrated_lufs"] - stem["integrated_lufs"] == pytest.approx(9.54, abs=0.1)
    assert stem["maximum_true_peak_dbtp"] == pytest.approx(-20.0, abs=0.1)
    assert len(stem["short_term_timeline"]) == 2


def test_report_insights_summarize_ownership_and_choose_duration_windows() -> None:
    active = np.array(
        [
            [True, True, False, False, False],
            [False, True, False, False, False],
            [False, False, False, True, True],
        ]
    )
    gains = np.where(active, 1.0, 10 ** (-6 / 20)).astype(np.float32)

    insights = build_report_insights(active, gains, frame_ms=1000)

    assert insights["health"] == {
        "single_owner_percent": 60.0,
        "multiple_owner_percent": 20.0,
        "unowned_percent": 20.0,
        "switches_per_minute": 12.0,
    }
    assert insights["window_seconds"] == 1.0
    assert [row["exclusive_percent"] for row in insights["track_summary"]] == [20.0, 0.0, 40.0]
    assert insights["speaker_share"][0]["overlap_percent"] == 20.0
    assert insights["speaker_share"][0]["unowned_percent"] == 20.0

    long_active = np.zeros((3, 120 * 60 * 50), dtype=bool)
    long_gains = np.ones_like(long_active, dtype=np.float32)
    long_insights = build_report_insights(long_active, long_gains, frame_ms=20)
    assert long_insights["window_seconds"] == 15.0

    overlong_active = np.zeros((3, 120 * 60 * 50 + 1), dtype=bool)
    overlong_gains = np.ones_like(overlong_active, dtype=np.float32)
    overlong_insights = build_report_insights(overlong_active, overlong_gains, frame_ms=20)
    assert overlong_insights["window_seconds"] == 30.0


def test_gain_envelope_preserves_active_and_attenuates_inactive() -> None:
    active = np.zeros((3, 100), dtype=bool)
    active[0, 20:40] = True
    gains = make_gain_envelopes(active, Settings())
    assert gains.shape == active.shape
    assert gains[0, 30] > 0.99
    assert gains[1, -1] == pytest.approx(10 ** (-6 / 20), abs=1e-4)
    assert np.all(gains <= 1.0)


def test_gain_envelope_applies_default_preroll_and_hold_on_intended_sides() -> None:
    active = np.zeros((3, 40), dtype=bool)
    active[0, 10] = True

    gains = make_gain_envelopes(active, Settings())
    floor_gain = 10 ** (-6 / 20)

    # Eight preroll frames: opening starts at frame 2. Twenty hold frames:
    # closing starts after frame 30.
    assert gains[0, :2] == pytest.approx(floor_gain)
    assert gains[0, 2] > gains[0, 1]
    assert np.all(np.diff(gains[0, 2:31]) >= 0)
    assert gains[0, 31] < gains[0, 30]


def test_gain_envelope_expands_exact_range_and_clips_at_boundaries() -> None:
    settings = Settings(
        frame_ms=20,
        preroll_ms=40,
        hold_ms=60,
        open_ms=20,
        close_ms=20,
    )
    active = np.zeros((3, 12), dtype=bool)
    active[0, 0] = True
    active[1, 6] = True
    active[2, 11] = True

    gains = make_gain_envelopes(active, settings)
    floor_gain = 10 ** (-6 / 20)

    assert gains[0] == pytest.approx([1.0] * 4 + [floor_gain] * 8)
    assert gains[1] == pytest.approx([floor_gain] * 4 + [1.0] * 6 + [floor_gain] * 2)
    assert gains[2] == pytest.approx([floor_gain] * 9 + [1.0] * 3)


def test_energetic_fallback_uses_each_stems_calibrated_noise_floor() -> None:
    energies = np.array(
        [
            [-20.0, -60.0, -60.0, -30.0, -60.0, -60.0, -60.0, -60.0],
            [-35.0, -10.0, -35.0, -34.0, -35.0, -35.0, -35.0, -35.0],
            [-70.0, -70.0, -30.0, -70.0, -70.0, -70.0, -70.0, -70.0],
        ],
        dtype=np.float32,
    )
    speech = np.zeros_like(energies, dtype=bool)
    speech[0, 0] = True
    speech[1, 1] = True
    speech[2, 2] = True

    active, calibration, floors = _classify_activity(energies, speech, ambiguity_db=3.0)

    assert calibration.tolist() == pytest.approx([0.0, 10.0, -10.0])
    assert floors.tolist() == pytest.approx([-60.0, -35.0, -70.0])
    assert active[:, 3].tolist() == [True, False, False]
    assert not np.any(active[:, 4:])


def test_validation_rejects_mismatched_frame_counts(tmp_path: Path) -> None:
    paths = []
    for index, frames in enumerate((100, 100, 99)):
        path = tmp_path / f"A0{index + 1}.wav"
        sf.write(path, np.zeros(frames, dtype=np.float32), 48000, subtype="FLOAT")
        paths.append(path)
    with pytest.raises(AutomixError, match="identical"):
        inspect_inputs(paths)


def test_validation_requires_three_files(tmp_path: Path) -> None:
    with pytest.raises(AutomixError, match="Exactly three"):
        inspect_inputs([tmp_path / "one.wav"])


def test_vad_adapter_passes_audio_before_model() -> None:
    sentinel = object()

    def timestamps(audio, model, **kwargs):
        assert isinstance(audio, np.ndarray)
        assert model is sentinel
        assert kwargs["sampling_rate"] == 16000
        return [{"start": 0.0, "end": 0.02}]

    mask = _speech_mask(np.ones(960, dtype=np.float32), 48000, sentinel, timestamps, 1)
    assert mask.tolist() == [True]


def test_bext_timestamp_is_preserved_and_offset(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    destination = tmp_path / "destination.wav"
    sf.write(source, np.zeros(10, dtype=np.float32), 48000, subtype="FLOAT")
    sf.write(destination, np.zeros(10, dtype=np.float32), 48000, subtype="FLOAT")

    # Add a minimal synthetic BWF chunk to the source.
    payload = bytearray(602)
    struct.pack_into("<Q", payload, 338, 1000)
    raw = source.read_bytes()
    data_at = raw.index(b"data")
    rebuilt = raw[:data_at] + struct.pack("<4sI", b"bext", len(payload)) + payload + raw[data_at:]
    rebuilt = rebuilt[:4] + struct.pack("<I", len(rebuilt) - 8) + rebuilt[8:]
    source.write_bytes(rebuilt)

    _inject_bext(source, destination, 250)
    copied = _read_riff_chunk(destination, b"bext")
    assert copied is not None
    assert struct.unpack_from("<Q", copied, 338)[0] == 1250


def test_diagnostics_csv_contains_activity_and_gain(tmp_path: Path) -> None:

    path = tmp_path / "diagnostics.csv"
    active = np.array([[True], [False], [True]])
    gains = np.array([[1.0], [0.5], [1.0]], dtype=np.float32)
    write_diagnostics(path, active, gains, 20)
    text = path.read_text(encoding="utf-8")
    assert "a02_gain_db" in text
    assert "0.000,1,0,1,0.000,-6.021,0.000" in text


def test_html_report_is_self_contained_and_escapes_track_names(tmp_path: Path) -> None:
    source_paths = [tmp_path / "A01 & host.wav", tmp_path / "A02.wav", tmp_path / "A03.wav"]
    infos = []
    for path in source_paths:
        sf.write(path, np.zeros(10, dtype=np.float32), 48000, subtype="FLOAT")
    infos = inspect_inputs(source_paths)
    destination = tmp_path / "report.html"
    gains = np.array([[1.0, 0.5], [1.0, 1.0], [0.5, 0.5]], dtype=np.float32)
    analysis = {
        "calibration_db": [0.0, -1.5, 3.0],
        "noise_floor_db": [-60.0, -59.0, -61.0],
        "active_percent": [50.0, 75.0, 25.0],
    }

    active = np.array([[True, False], [False, True], [False, False]])
    write_html_report(destination, infos, Settings(), gains, active, analysis)

    text = destination.read_text(encoding="utf-8")
    assert "<!doctype html>" in text
    assert "Automix health" in text
    assert "Attenuation overview" in text
    assert "Speaker ownership by section" in text
    assert "Moments to review" in text
    assert '"timeline":[' in text
    assert '"health":{' in text
    assert '"speaker_share":[' in text
    assert '"review_moments":[' in text
    assert "A01 & host" in text
    assert '<script src="http' not in text


def test_parse_powershell_drag_drop_paths_with_backtick_spaces() -> None:
    raw = (
        r"C:\Users\User\Downloads\chopshow` podcast` 155_A03.wav "
        r"C:\Users\User\Downloads\chopshow` podcast` 155_A02.wav "
        r"C:\Users\User\Downloads\chopshow` podcast` 155_A01.wav "
    )
    paths = parse_dropped_paths(raw)
    assert [path.name for path in paths] == [
        "chopshow podcast 155_A03.wav",
        "chopshow podcast 155_A02.wav",
        "chopshow podcast 155_A01.wav",
    ]
