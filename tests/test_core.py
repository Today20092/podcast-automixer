import json
import math
import struct
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from podcast_automixer.cli import parse_dropped_paths, parser
from podcast_automixer.core import (
    AutomixError,
    Settings,
    _classify_activity,
    _inject_bext,
    _read_riff_chunk,
    _speech_mask,
    analyze,
    inspect_inputs,
    make_gain_envelopes,
    write_diagnostics,
    write_report,
)
from podcast_automixer.loudness import (
    KWeightFilter,
    _StreamingMeter,
    analyze_rendered_loudness,
    k_weight,
)
from podcast_automixer.report import build_report_insights, write_html_report


def test_k_weighting_favors_voice_band_over_low_frequency_rumble() -> None:
    samplerate = 48000
    seconds = np.arange(samplerate, dtype=np.float64) / samplerate
    voice_band = np.sin(2 * np.pi * 1000 * seconds)
    rumble = np.sin(2 * np.pi * 30 * seconds)

    voice_rms = np.sqrt(np.mean(np.square(k_weight(voice_band, samplerate))))
    rumble_rms = np.sqrt(np.mean(np.square(k_weight(rumble, samplerate))))

    assert voice_rms > rumble_rms * 2


def test_streaming_k_weighting_matches_single_pass() -> None:
    samplerate = 48000
    rng = np.random.default_rng(42)
    audio = rng.normal(0, 0.1, samplerate * 2)
    expected = k_weight(audio, samplerate)

    weighting = KWeightFilter(samplerate)
    actual = np.concatenate(
        [weighting.process(audio[:12345]), weighting.process(audio[12345:54321]),
         weighting.process(audio[54321:])]
    )

    assert actual == pytest.approx(expected, abs=1e-12)


def test_analysis_is_segment_size_independent_across_speech_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    samplerate = 16000
    audio = np.zeros(samplerate * 3, dtype=np.float32)
    t = np.arange(len(audio)) / samplerate
    utterances = ((t >= 0.8) & (t < 1.2)) | ((t >= 1.8) & (t < 2.2))
    audio[utterances] = 0.2 * np.sin(2 * np.pi * 440 * t[utterances])
    paths = []
    for index, scale in enumerate((1.0, 0.1, 0.05)):
        path = tmp_path / f"stem-{index}.wav"
        sf.write(path, audio * scale, samplerate, subtype="FLOAT")
        paths.append(path)

    def timestamps(sidechain, model, **kwargs):
        del model, kwargs
        voiced = np.abs(sidechain) > 0.005
        edges = np.diff(np.pad(voiced.astype(np.int8), (1, 1)))
        starts = np.flatnonzero(edges == 1)
        ends = np.flatnonzero(edges == -1)
        return [
            {"start": start, "end": end}
            for start, end in zip(starts, ends, strict=True)
        ]

    monkeypatch.setattr("podcast_automixer.core._load_vad", lambda: (object(), timestamps))
    infos = inspect_inputs(paths)
    _, one_second, _ = analyze(infos, Settings(segment_seconds=1))
    _, two_seconds, _ = analyze(infos, Settings(segment_seconds=2))

    assert np.array_equal(one_second, two_seconds)
    assert np.all(one_second[0, 45:55])
    assert np.all(one_second[0, 95:105])


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
    assert stem["maximum_estimated_true_peak_dbtp"] == pytest.approx(-20.0, abs=0.1)
    assert len(stem["short_term_timeline"]) == 2


def test_estimated_peak_is_continuous_across_chunk_boundaries() -> None:
    samplerate = 48000
    samples = np.arange(400, dtype=np.float64)
    # A phase-offset high-frequency tone has intersample peaks and puts one at the split.
    audio = 0.5 * np.sin(2 * np.pi * 17000 * samples / samplerate + 0.37)

    whole = _StreamingMeter(samplerate)
    whole.add(audio)
    chunked = _StreamingMeter(samplerate)
    chunked.add(audio[:173])
    chunked.add(audio[173:])

    key = "maximum_estimated_true_peak_dbtp"
    assert chunked.result()[key] == pytest.approx(whole.result()[key], abs=1e-12)


def test_silent_estimated_peak_serializes_as_null() -> None:
    meter = _StreamingMeter(48000)
    meter.add(np.zeros(1000, dtype=np.float64))

    assert meter.result()["maximum_estimated_true_peak_dbtp"] is None


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


@pytest.mark.parametrize("frame_ms", [10, 20])
def test_gain_envelope_matches_closed_form_one_pole_response(frame_ms: int) -> None:
    settings = Settings(
        frame_ms=frame_ms,
        preroll_ms=0,
        hold_ms=0,
        open_ms=100,
        close_ms=200,
    )
    active = np.zeros((3, 1000 // frame_ms), dtype=bool)
    start = 100 // frame_ms
    stop = 500 // frame_ms
    active[0, start:stop] = True

    gains = make_gain_envelopes(active, settings)
    floor_gain = 10 ** (settings.attenuation_db / 20)
    for elapsed_ms in (100, 200, 300):
        index = start + elapsed_ms // frame_ms - 1
        expected = 1.0 - (1.0 - floor_gain) * math.exp(-elapsed_ms / settings.open_ms)
        assert gains[0, index] == pytest.approx(expected, abs=1e-6)

    opening_end = gains[0, stop - 1]
    for elapsed_ms in (100, 200, 400):
        index = stop + elapsed_ms // frame_ms - 1
        expected = floor_gain + (opening_end - floor_gain) * math.exp(
            -elapsed_ms / settings.close_ms
        )
        assert gains[0, index] == pytest.approx(expected, abs=1e-6)


def test_gain_envelope_retargets_smoothly_from_current_value() -> None:
    settings = Settings(frame_ms=20, preroll_ms=0, hold_ms=0, open_ms=100, close_ms=100)
    active = np.zeros((3, 20), dtype=bool)
    active[0, 2:7] = True
    active[0, 9:] = True

    gains = make_gain_envelopes(active, settings)[0]

    assert gains[7] < gains[6]
    assert gains[8] < gains[7]
    assert gains[9] > gains[8]
    assert gains[9] < 1.0


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

    assert gains[0, :4] == pytest.approx([1.0] * 4)
    assert np.all(np.diff(gains[0, 4:]) < 0)
    assert gains[1, :4] == pytest.approx([floor_gain] * 4)
    assert np.all(np.diff(gains[1, 4:10]) > 0)
    assert np.all(np.diff(gains[1, 10:]) < 0)
    assert gains[2, :9] == pytest.approx([floor_gain] * 9)
    assert np.all(np.diff(gains[2, 9:]) > 0)


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
        assert kwargs["return_seconds"] is False
        assert kwargs["min_silence_duration_ms"] == 100
        assert kwargs["speech_pad_ms"] == 30
        return [{"start": 0, "end": 320}]

    mask = _speech_mask(
        np.ones(960, dtype=np.float32),
        48000,
        sentinel,
        timestamps,
        1,
        frame_samples=960,
    )
    assert mask.tolist() == [True]


def test_vad_adapter_maps_sample_boundaries_with_floor_and_ceiling() -> None:
    def timestamps(audio, model, **kwargs):
        del audio, model, kwargs
        return [{"start": 321, "end": 641}]

    mask = _speech_mask(
        np.ones(3840, dtype=np.float32),
        48000,
        object(),
        timestamps,
        4,
        frame_samples=960,
    )

    assert mask.tolist() == [False, True, True, False]


def test_vad_adapter_maps_partial_final_frame() -> None:
    def timestamps(audio, model, **kwargs):
        del audio, model, kwargs
        return [{"start": 320, "end": 333}]

    mask = _speech_mask(
        np.ones(1000, dtype=np.float32),
        48000,
        object(),
        timestamps,
        2,
        trim_samples=1000,
        frame_samples=960,
    )

    assert mask.tolist() == [False, True]


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
    assert "Opening time constant" in text
    assert "Closing time constant" in text
    assert "about 63%" in text
    assert '"timeline":[' in text
    assert '"health":{' in text
    assert '"speaker_share":[' in text
    assert '"review_moments":[' in text
    assert "A01 & host" in text
    assert '<script src="http' not in text


def test_cli_help_labels_envelope_controls_as_time_constants() -> None:
    help_text = parser().format_help()

    assert "--open-ms MS" in help_text
    assert "Opening time constant in milliseconds" in help_text
    assert "--close-ms MS" in help_text
    assert "Closing time constant in milliseconds" in help_text


def test_json_report_labels_envelope_time_constants(tmp_path: Path) -> None:
    source_paths = [tmp_path / f"A0{index}.wav" for index in range(1, 4)]
    for path in source_paths:
        sf.write(path, np.zeros(10, dtype=np.float32), 48000, subtype="FLOAT")
    destination = tmp_path / "report.json"

    write_report(
        destination,
        inspect_inputs(source_paths),
        Settings(open_ms=75, close_ms=600),
        np.ones((3, 1), dtype=np.float32),
        {},
    )

    settings = json.loads(destination.read_text(encoding="utf-8"))["settings"]
    assert settings["opening_time_constant_ms"] == 75
    assert settings["closing_time_constant_ms"] == 600
    assert settings["open_ms"] == 75
    assert settings["close_ms"] == 600


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
