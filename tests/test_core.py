import json
import math
import time
import tracemalloc
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from podcast_automixer.cli import parser
from podcast_automixer.core import (
    AutomixError,
    Settings,
    _classify_activity,
    _speech_mask,
    analyze,
    expand_activity_targets,
    inspect_inputs,
    make_gain_envelopes,
)
from podcast_automixer.loudness import (
    KWeightFilter,
    _StreamingMeter,
    analyze_rendered_loudness,
    k_weight,
)
from podcast_automixer.report import (
    Report,
    build_report_insights,
    write_diagnostics,
    write_html_report,
    write_json_report,
)


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
        [
            weighting.process(audio[:12345]),
            weighting.process(audio[12345:54321]),
            weighting.process(audio[54321:]),
        ]
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
        return [{"start": start, "end": end} for start, end in zip(starts, ends, strict=True)]

    monkeypatch.setattr("podcast_automixer.core._load_vad", lambda: (object(), timestamps))
    infos = inspect_inputs(paths)
    one_second = analyze(infos, Settings(segment_seconds=1))
    two_seconds = analyze(infos, Settings(segment_seconds=2))

    assert np.array_equal(one_second.active, two_seconds.active)
    assert np.all(one_second.active[0, 45:55])
    assert np.all(one_second.active[0, 95:105])
    assert one_second.start_sample == 0
    assert one_second.sample_count == samplerate * 3
    assert one_second.samples_per_frame == 320


@pytest.mark.parametrize("track_count", [1, 2, 4])
def test_analysis_supports_one_or_more_tracks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, track_count: int
) -> None:
    samplerate = 16000
    samples = np.arange(samplerate, dtype=np.float32)
    audio = 0.1 * np.sin(2 * np.pi * 440 * samples / samplerate)
    paths = []
    for index in range(track_count):
        path = tmp_path / f"stem-{index}.wav"
        sf.write(path, audio, samplerate, subtype="FLOAT")
        paths.append(path)

    def timestamps(sidechain, model, **kwargs):
        del model, kwargs
        return [{"start": 0, "end": len(sidechain)}]

    monkeypatch.setattr("podcast_automixer.core._load_vad", lambda: (object(), timestamps))
    result = analyze(inspect_inputs(paths), Settings(segment_seconds=1))

    assert result.active.shape[0] == track_count
    assert result.gains.shape[0] == track_count
    assert result.calibration_db.shape == (track_count,)
    assert result.noise_floor_db.shape == (track_count,)


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
    assert stem["maximum_momentary_lufs"] == pytest.approx(-23.05, abs=0.25)
    assert stem["maximum_short_term_lufs"] == pytest.approx(-23.05, abs=0.25)
    assert stem["loudness_range_lu"] == pytest.approx(2.34, abs=0.1)
    assert program["integrated_lufs"] - stem["integrated_lufs"] == pytest.approx(9.54, abs=0.1)
    assert stem["maximum_estimated_true_peak_dbtp"] == pytest.approx(-20.0, abs=0.1)
    assert len(stem["short_term_timeline"]) == 2
    assert stem["short_term_timeline"][0] == {
        "seconds": 0.0,
        "lufs": pytest.approx(-23.05, abs=0.25),
    }


def test_loudness_report_exposes_progress_until_measurement_finishes(tmp_path: Path) -> None:
    samplerate = 8000
    tone = np.zeros(samplerate * 21, dtype=np.float32)
    paths = []
    for index in range(2):
        path = tmp_path / f"stem-{index}.wav"
        sf.write(path, tone, samplerate, subtype="FLOAT")
        paths.append(path)
    events: list[tuple[str, int, int, int]] = []

    analyze_rendered_loudness(paths, progress=lambda *event: events.append(event))

    assert events
    assert {event[0] for event in events} == {"Measuring loudness"}
    assert events[-1][2] == events[-1][3]
    assert events[-2][2] == events[-1][3] - 1
    assert [event[2] for event in events] == sorted(event[2] for event in events)


def test_loudness_measurement_is_continuous_across_chunk_boundaries() -> None:
    samplerate = 48000
    samples = np.arange(samplerate * 4, dtype=np.float64)
    # A phase-offset high-frequency tone has intersample peaks and puts one at the split.
    audio = 0.5 * np.sin(2 * np.pi * 17000 * samples / samplerate + 0.37)

    whole = _StreamingMeter(samplerate)
    whole.add(audio)
    chunked = _StreamingMeter(samplerate)
    for chunk in np.array_split(audio, [173, 48001, 100003]):
        chunked.add(chunk)

    whole_result = whole.result()
    chunked_result = chunked.result()
    for key in (
        "integrated_lufs",
        "maximum_momentary_lufs",
        "maximum_short_term_lufs",
        "loudness_range_lu",
        "maximum_estimated_true_peak_dbtp",
    ):
        assert chunked_result[key] == pytest.approx(whole_result[key], abs=1e-10)
    assert chunked_result["short_term_timeline"] == pytest.approx(
        whole_result["short_term_timeline"]
    )


def test_loudness_meter_retains_only_bounded_audio_windows() -> None:
    meter = _StreamingMeter(48000)
    chunk = np.zeros(48000, dtype=np.float32)

    for _ in range(20):
        meter.add(chunk)

    assert not hasattr(meter, "peak_audio")
    assert len(meter.momentary.remainder) < round(0.4 * meter.samplerate)
    assert len(meter.short_term.remainder) < round(3.0 * meter.samplerate)


def test_long_loudness_measurement_is_fast_and_retains_bounded_audio() -> None:
    samplerate = 8000
    ten_seconds = np.zeros(samplerate * 10, dtype=np.float32)

    peaks = []
    started = time.perf_counter()
    for chunk_count in (6, 60):
        meter = _StreamingMeter(samplerate)
        tracemalloc.start()
        for _ in range(chunk_count):
            meter.add(ten_seconds)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peaks.append(peak)
    elapsed = time.perf_counter() - started

    assert elapsed < 5.0
    assert peaks[1] - peaks[0] < 1024 * 1024
    assert len(meter.momentary.remainder) < round(0.4 * samplerate)
    assert len(meter.short_term.remainder) < round(3.0 * samplerate)


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

    gain_db = 20 * np.log10(np.maximum(gains, 1e-9))
    insights = build_report_insights(active, gain_db, frame_ms=1000)

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
    long_insights = build_report_insights(long_active, np.zeros_like(long_gains), frame_ms=20)
    assert long_insights["window_seconds"] == 15.0

    overlong_active = np.zeros((3, 120 * 60 * 50 + 1), dtype=bool)
    overlong_gains = np.ones_like(overlong_active, dtype=np.float32)
    overlong_insights = build_report_insights(
        overlong_active, np.zeros_like(overlong_gains), frame_ms=20
    )
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


def test_diagnostic_target_and_gain_share_the_same_expanded_timeline() -> None:
    active = np.array([[False, True, False, False]], dtype=bool)
    settings = Settings(frame_ms=100, preroll_ms=100, hold_ms=100, attenuation_db=-12)

    expanded = expand_activity_targets(active, settings)
    gains = make_gain_envelopes(active, settings, expanded=expanded)

    assert expanded.tolist() == [[True, True, True, False]]
    assert gains.shape == active.shape
    assert gains[0, 3] < gains[0, 2]


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


def test_validation_requires_at_least_one_file() -> None:
    with pytest.raises(AutomixError, match="At least one"):
        inspect_inputs([])


def test_validation_accepts_more_than_three_files(tmp_path: Path) -> None:
    paths = []
    for index in range(4):
        path = tmp_path / f"A0{index + 1}.wav"
        sf.write(path, np.zeros(100, dtype=np.float32), 48000, subtype="FLOAT")
        paths.append(path)

    assert len(inspect_inputs(paths)) == 4


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


def test_diagnostics_csv_contains_activity_and_gain(tmp_path: Path) -> None:
    path = tmp_path / "diagnostics.csv"
    active = np.array([[True], [False], [True], [False]])
    gains = np.array([[1.0], [0.5], [1.0], [0.25]], dtype=np.float32)
    report = Report([], Settings(), gains, active, {})
    rows = report.diagnostics_rows()
    assert iter(rows) is rows

    write_diagnostics(path, report)
    text = path.read_text(encoding="utf-8")
    assert "a04_gain_db" in text
    assert "0.000,1,0,1,0,0.000,-6.021,0.000,-12.041" in text


@pytest.mark.parametrize("track_count", [2, 4])
def test_report_payloads_support_two_or_more_tracks(tmp_path: Path, track_count: int) -> None:
    source_paths = [tmp_path / f"A{index + 1:02}.wav" for index in range(track_count)]
    for path in source_paths:
        sf.write(path, np.zeros(10, dtype=np.float32), 48000, subtype="FLOAT")
    active = np.zeros((track_count, 2), dtype=bool)
    gains = np.ones((track_count, 2), dtype=np.float32)
    analysis = {
        "calibration_db": [0.0] * track_count,
        "noise_floor_db": [-60.0] * track_count,
        "active_percent": [0.0] * track_count,
    }

    payload = Report(
        inspect_inputs(source_paths), Settings(), gains, active, analysis
    ).html_payload()

    assert len(payload["tracks"]) == track_count
    assert len(payload["track_summary"]) == track_count
    assert len(payload["timeline"][0]["gain_db"]) == track_count


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
    write_html_report(destination, Report(infos, Settings(), gains, active, analysis))

    text = destination.read_text(encoding="utf-8")
    assert "<!doctype html>" in text
    assert "Automix health" in text
    assert "Review event timeline" in text
    assert "Automix activity timeline" in text
    assert "Gain reduction by microphone" in text
    assert "Conversation balance" in text
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

    write_json_report(
        destination,
        Report(
            inspect_inputs(source_paths),
            Settings(open_ms=75, close_ms=600),
            np.ones((3, 1), dtype=np.float32),
            np.ones((3, 1), dtype=bool),
            {},
        ),
    )

    settings = json.loads(destination.read_text(encoding="utf-8"))["settings"]
    assert settings["opening_time_constant_ms"] == 75
    assert settings["closing_time_constant_ms"] == 600
    assert settings["open_ms"] == 75
    assert settings["close_ms"] == 600
