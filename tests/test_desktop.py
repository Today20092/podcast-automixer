import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from time import monotonic, sleep
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

import podcast_automixer.desktop as desktop
from podcast_automixer.desktop import DesktopBridge, _dialog_path, _dropped_file_paths
from podcast_automixer.engine import AutomixEngine
from podcast_automixer.loudness import analyze_comparison_playback


def _valid_preview_inspection(source: Path) -> SimpleNamespace:
    info = sf.info(source)
    return SimpleNamespace(
        inputs=[SimpleNamespace(frames=info.frames, samplerate=info.samplerate)], problems=[]
    )


def test_bridge_validates_only_wav_family_recording_sets() -> None:
    with pytest.raises(ValueError, match="WAV-family"):
        DesktopBridge(AutomixEngine()).inspect_recording_set(["voice.mp3"])


def test_native_drop_paths_require_resolved_paths_and_remove_duplicates() -> None:
    assert _dropped_file_paths(
        {
            "dataTransfer": {
                "files": [
                    {"pywebviewFullPath": r"C:\\Recordings\\host.wav"},
                    {"pywebviewFullPath": r"C:\\Recordings\\guest.wav"},
                    {"pywebviewFullPath": r"C:\\Recordings\\host.wav"},
                    {"name": "unresolved.wav"},
                ]
            }
        }
    ) == [r"C:\\Recordings\\host.wav", r"C:\\Recordings\\guest.wav"]
    assert _dropped_file_paths({"dataTransfer": {"files": [{"name": "voice.wav"}]}}) == []


@pytest.mark.parametrize(
    ("selected", "expected"),
    [
        ((r"C:\\Users\\Ada\\Downloads",), r"C:\\Users\\Ada\\Downloads"),
        ([r"C:\\Users\\Ada\\Downloads"], r"C:\\Users\\Ada\\Downloads"),
        (r"C:\\Users\\Ada\\Downloads", r"C:\\Users\\Ada\\Downloads"),
        (None, None),
        ((), None),
    ],
)
def test_folder_dialog_returns_one_path_not_container_repr(
    selected: object, expected: str | None
) -> None:
    assert _dialog_path(selected) == expected


def test_desktop_drop_boundary_uses_pywebview_paths_and_rejects_bad_recordings() -> None:
    page = (Path(desktop.__file__).parent / "desktop.html").read_text(encoding="utf-8")

    assert "window.receiveDroppedPaths=next=>add(next)" in page
    assert "file.path" not in page
    assert "Checking recordings" in page
    assert "Could not resolve a file path" in page

    bridge = Path(desktop.__file__).read_text(encoding="utf-8")
    assert "pywebviewFullPath" in bridge
    assert "prevent_default=True" in bridge
    assert "stop_propagation=True" in bridge


@pytest.mark.parametrize("value", ["__import__('os').system('whoami')", ["../source.wav"]])
def test_bridge_rejects_non_contract_and_traversal_inputs(value: object) -> None:
    with pytest.raises(ValueError):
        DesktopBridge(AutomixEngine()).inspect_recording_set(value)


def test_preview_session_path_is_app_owned_isolated_and_cleaned(tmp_path: Path) -> None:
    first = DesktopBridge(temp_directory=tmp_path)
    second = DesktopBridge(temp_directory=tmp_path)

    assert first._preview_root == tmp_path / "podcast-automixer-preview-sessions"
    assert first._preview_session.parent == first._preview_root
    assert first._preview_session != second._preview_session
    assert "Preview Runs" not in str(first._preview_session)
    assert "('" not in str(first._preview_session)

    session = first._preview_session
    first.close_session()
    assert not session.exists()
    assert second._preview_session.exists()
    second.close_session()


@pytest.mark.parametrize(
    ("temporary", "expected"),
    [
        (
            PureWindowsPath("C:/Users/Ada/AppData/Local/Temp"),
            PureWindowsPath("C:/Users/Ada/AppData/Local/Temp/podcast-automixer-preview-sessions"),
        ),
        (
            PurePosixPath("/tmp"),
            PurePosixPath("/tmp/podcast-automixer-preview-sessions"),
        ),
    ],
)
def test_preview_root_construction_preserves_platform_path_semantics(
    temporary: PureWindowsPath | PurePosixPath,
    expected: PureWindowsPath | PurePosixPath,
) -> None:
    assert DesktopBridge._preview_root_directory(temporary) == expected


def test_crash_recovery_removes_only_stale_positively_owned_sessions(tmp_path: Path) -> None:
    root = tmp_path / DesktopBridge._PREVIEW_ROOT_NAME
    stale = root / "session-stale"
    recent = root / "session-recent"
    unmarked = root / "session-unmarked"
    unrelated = root / "other-folder"
    for directory in (stale, recent, unmarked, unrelated):
        directory.mkdir(parents=True)
        (directory / "audio.wav").write_bytes(b"keep unless owned and stale")
    for directory in (stale, recent):
        marker = directory / DesktopBridge._PREVIEW_MARKER
        marker.write_text(DesktopBridge._PREVIEW_MARKER_CONTENT, encoding="utf-8")
    old = 1_000.0
    os.utime(stale / DesktopBridge._PREVIEW_MARKER, (old, old))

    removed = DesktopBridge._recover_stale_preview_sessions(
        root, now=old + DesktopBridge._PREVIEW_RETENTION_SECONDS + 1
    )

    assert removed == [stale]
    assert not stale.exists()
    assert recent.exists()
    assert unmarked.exists()
    assert unrelated.exists()


def test_desktop_shell_declares_accessible_compact_and_reduced_motion_contract() -> None:
    page = (Path(desktop.__file__).parent / "desktop.html").read_text(encoding="utf-8")

    for requirement in (
        "@media(max-width:780px)",
        "@media(prefers-reduced-motion:reduce)",
        "focus-visible",
        'role="status"',
        'role="alert"',
        'role="slider"',
    ):
        assert requirement in page
    assert "choose_preview_directory" not in page
    assert 'id="choose-destination"' not in page
    assert "api.start_preview(paths,Number(startTime.value),Number(durationInput.value))" in page
    assert 'id="export-preview"' in page
    assert "api.export_preview()" in page


def test_bridge_inspection_keeps_each_recording_visible_with_technical_details(
    tmp_path: Path,
) -> None:
    first = tmp_path / "host.wav"
    second = tmp_path / "guest.wav"
    sf.write(first, np.zeros(100, dtype=np.float32), 48000, subtype="FLOAT")
    sf.write(second, np.zeros(99, dtype=np.float32), 48000, subtype="FLOAT")

    inspection = DesktopBridge(AutomixEngine()).inspect_recording_set([str(first), str(second)])

    assert [item["path"] for item in inspection["inputs"]] == [str(first), str(second)]
    assert all(item["channels"] == 1 for item in inspection["inputs"])
    assert all(item["subtype"] == "FLOAT" for item in inspection["inputs"])
    assert inspection["problems"] == [
        {
            "code": "invalid_recording_set",
            "message": (
                "Inputs must have identical sample rate, channels, frame count, and subtype."
            ),
        }
    ]


def test_bridge_runs_selected_preview_off_the_calling_thread_and_cancels(tmp_path: Path) -> None:
    def fake_preview(_paths, _output, **kwargs):
        assert kwargs["start_seconds"] == 2.0
        assert kwargs["duration_seconds"] == 30.0
        assert _output.parent == bridge._preview_session
        assert _output.name == "run-0001"
        while True:
            kwargs["cancellation"].raise_if_cancelled()
            sleep(0.01)

    class FakeEngine:
        @staticmethod
        def inspect(_paths):
            return _valid_preview_inspection(source)

        preview = staticmethod(fake_preview)

    source = tmp_path / "voice.wav"
    sf.write(source, np.zeros(48_000 * 40, dtype=np.float32), 48_000, subtype="FLOAT")
    bridge = DesktopBridge(FakeEngine())
    bridge._last_success = {"outputs": ["previous-preview.wav"]}
    result = bridge.start_preview([str(source)], 2.0, 30.0)
    assert result == {"state": "running", "start_seconds": 2.0, "duration_seconds": 30.0}
    started = monotonic()
    assert bridge.cancel_preview()["state"] == "cancelling"
    while bridge.status()["state"] != "cancelled" and monotonic() - started < 1:
        sleep(0.01)
    assert bridge.status()["state"] == "cancelled"
    assert bridge.status()["result"]["outputs"] == ["previous-preview.wav"]


def test_bridge_clips_preview_range_at_recording_end(tmp_path: Path) -> None:
    source = tmp_path / "voice.wav"
    sf.write(source, np.zeros(48_000 * 8, dtype=np.float32), 48_000, subtype="FLOAT")

    class FakeEngine:
        @staticmethod
        def inspect(_paths):
            return _valid_preview_inspection(source)

        @staticmethod
        def preview(_paths, _output, **kwargs):
            assert kwargs["start_seconds"] == 3.0
            assert kwargs["duration_seconds"] == 5.0
            kwargs["cancellation"].raise_if_cancelled()
            return SimpleNamespace(
                outputs=[], report=tmp_path / "report.json", html_report=tmp_path / "report.html"
            )

    bridge = DesktopBridge(FakeEngine())
    result = bridge.start_preview([str(source)], 7.0, 30.0)
    assert result["start_seconds"] == 3.0
    assert result["duration_seconds"] == 5.0
    while bridge.status()["state"] != "complete":
        sleep(0.01)


def test_comparison_diagnostics_serialize_coherent_engine_frames() -> None:
    analysis = SimpleNamespace(
        gains=np.array([[1.0, 0.8, 0.4, 0.7]], dtype=np.float32),
        detected_speech=np.array([[True, False, False, True]]),
        target_open=np.array([[True, False, False, True]]),
        frame_ms=20,
        attenuation_db=-12.0,
    )

    track = DesktopBridge._comparison_diagnostics(
        SimpleNamespace(analysis=analysis), [Path("host.wav")]
    )[0]

    assert track["name"] == "host"
    assert [frame["response"] for frame in track["frames"]] == [
        "open",
        "closing",
        "closing",
        "opening",
    ]
    assert track["frames"][1]["seconds"] == 0.02
    assert track["frames"][1]["speech"] is False
    assert track["frames"][1]["target_open"] is False
    assert track["frames"][1]["gain_db"] == pytest.approx(20 * np.log10(0.8))


def test_comparison_diagnostics_preserve_recording_order_and_report_colors() -> None:
    track_count = 8
    analysis = SimpleNamespace(
        gains=np.ones((track_count, 1), dtype=np.float32),
        detected_speech=np.ones((track_count, 1), dtype=bool),
        target_open=np.ones((track_count, 1), dtype=bool),
        attenuation_db=-24.0,
        frame_ms=20,
    )
    paths = [Path(f"mic-{index}.wav") for index in range(track_count, 0, -1)]

    diagnostics = DesktopBridge._comparison_diagnostics(SimpleNamespace(analysis=analysis), paths)

    assert [track["name"] for track in diagnostics] == [path.stem for path in paths]
    assert [track["id"] for track in diagnostics] == [f"track-{index}" for index in range(1, 9)]
    assert len({track["color"] for track in diagnostics}) == 8


@pytest.mark.parametrize("analysis", [None, SimpleNamespace(detected_speech=None, target_open=None)])
def test_comparison_diagnostics_handle_missing_analysis(analysis: object | None) -> None:
    assert DesktopBridge._comparison_diagnostics(SimpleNamespace(analysis=analysis), [Path("mic.wav")]) == []


def test_comparison_playback_measures_programs_without_changing_audio(tmp_path: Path) -> None:
    original = tmp_path / "original.wav"
    rendered = tmp_path / "rendered.wav"
    samples = np.sin(np.linspace(0, 100, 48_000, dtype=np.float32)) * 0.25
    sf.write(original, samples, 48_000, subtype="FLOAT")
    sf.write(rendered, samples * 0.5, 48_000, subtype="FLOAT")
    bridge = DesktopBridge()
    bridge._last_success = {
        "paths": [str(original)],
        "outputs": [str(rendered)],
        "start_seconds": 0.0,
        "duration_seconds": 1.0,
    }

    comparison = bridge.comparison_playback()

    assert comparison["standard"] == "ITU-R BS.1770 / EBU R 128"
    assert comparison["playback_gain_db"]["original"] < 0
    assert sf.read(original, dtype="float32")[0].max() == pytest.approx(samples.max())


@pytest.mark.parametrize("path_count", [1, 2, 3])
def test_comparison_playback_payload_and_renderer_share_program_sum_topology(
    tmp_path: Path, path_count: int
) -> None:
    samples = np.sin(np.linspace(0, 200, 48_000, dtype=np.float32)) * 0.1
    originals = []
    rendered = []
    for index in range(path_count):
        original = tmp_path / f"original-{index}.wav"
        automixed = tmp_path / f"automixed-{index}.wav"
        sf.write(original, samples, 48_000, subtype="FLOAT")
        sf.write(automixed, samples, 48_000, subtype="FLOAT")
        originals.append(original)
        rendered.append(automixed)

    comparison = analyze_comparison_playback(originals, rendered, 0.0, 1.0)
    original_lufs = comparison["monitoring_mix"]["integrated_lufs"]
    automixed_lufs = comparison["automixed_virtual_program"]["integrated_lufs"]

    assert original_lufs == pytest.approx(automixed_lufs, abs=0.5)
    assert comparison["playback_gain_db"]["original"] == pytest.approx(
        comparison["playback_gain_db"]["automixed"]
    )
    if path_count == 3:
        assert (
            original_lufs
            > analyze_comparison_playback(originals[:1], rendered[:1], 0.0, 1.0)["monitoring_mix"][
                "integrated_lufs"
            ]
            + 9.0
        )

    renderer = (Path(desktop.__file__).parent / "comparison_playback.js").read_text(
        encoding="utf-8"
    )
    assert "/ paths.length" not in renderer
    assert "const source = context.createMediaElementSource(item)" in renderer
    assert "master.connect(context.destination)" in renderer
    assert "item.dataset.offset = offset" in renderer
    assert "seek(position()" in renderer


def test_difference_playback_uses_aligned_loudness_matched_signed_sum() -> None:
    renderer = (Path(desktop.__file__).parent / "comparison_playback.js").read_text(
        encoding="utf-8"
    )

    assert "bus('difference:original', -originalGain)" in renderer
    assert "bus('difference:automixed', automixedGain)" in renderer
    assert "source.connect(buses[`difference:${name}`])" in renderer
    assert "item.dataset.offset = offset" in renderer
    assert "audio.map(item => item.play())" in renderer

    original = np.array([0.25, -0.5, 0.75], dtype=np.float32)
    identical = original.copy()
    attenuated = original * 0.5
    assert np.allclose(identical - original, 0.0, atol=np.finfo(np.float32).eps)
    assert np.allclose(attenuated - original, [-0.125, 0.25, -0.375])


def test_difference_switching_and_shared_output_protection_are_in_renderer() -> None:
    renderer = (Path(desktop.__file__).parent / "comparison_playback.js").read_text(
        encoding="utf-8"
    )

    assert 'data-program="difference"' in renderer
    assert "select('difference')" in renderer
    assert "context.createDynamicsCompressor()" in renderer
    assert "node.connect(protection)" in renderer
    assert "protection.connect(master)" in renderer
    assert "master.connect(context.destination)" in renderer
    assert "Difference = Automixed − Original" in renderer
    assert "not a deliverable" in renderer


def test_comparison_playback_peak_protection_is_in_both_reported_trims(
    tmp_path: Path,
) -> None:
    samples = np.sin(np.linspace(0, 200, 48_000, dtype=np.float32)) * 0.8
    originals = []
    rendered = []
    for index in range(2):
        original = tmp_path / f"original-hot-{index}.wav"
        automixed = tmp_path / f"automixed-hot-{index}.wav"
        sf.write(original, samples, 48_000, subtype="FLOAT")
        sf.write(automixed, samples, 48_000, subtype="FLOAT")
        originals.append(original)
        rendered.append(automixed)

    comparison = analyze_comparison_playback(originals, rendered, 0.0, 1.0)

    assert comparison["peak_protection_db"] < 0
    for name, result in (
        ("original", comparison["monitoring_mix"]),
        ("automixed", comparison["automixed_virtual_program"]),
    ):
        assert (
            result["maximum_estimated_true_peak_dbtp"] + comparison["playback_gain_db"][name]
            <= 0.01
        )


def test_failed_replacement_keeps_the_last_successful_preview_and_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "voice.wav"
    rendered = tmp_path / "rendered.wav"
    report = tmp_path / "podcast-automix-report.html"
    sf.write(source, np.zeros(48_000 * 10, dtype=np.float32), 48_000, subtype="FLOAT")
    sf.write(rendered, np.zeros(48_000 * 10, dtype=np.float32), 48_000, subtype="FLOAT")
    report.write_text("<html></html>", encoding="utf-8")

    class FakeEngine:
        @staticmethod
        def inspect(_paths):
            return _valid_preview_inspection(source)

        @staticmethod
        def preview(_paths, _output, **kwargs):
            if kwargs["start_seconds"]:
                raise RuntimeError("disk is unavailable")
            return SimpleNamespace(
                outputs=[rendered], report=tmp_path / "report.json", html_report=report
            )

    bridge = DesktopBridge(FakeEngine())
    bridge.start_preview([str(source)])
    while bridge.status()["state"] != "complete":
        sleep(0.01)
    bridge.start_preview([str(source)], 1.0)
    while bridge.status()["state"] != "failed":
        sleep(0.01)

    status = bridge.status()
    assert status["result"]["outputs"] == [str(rendered)]
    assert status["result"]["html_report"] == str(report)
    assert bridge.preview_mix_report()["url"] == report.as_uri()
    opened: list[str] = []
    monkeypatch.setattr(desktop.webbrowser, "open", opened.append)
    assert bridge.open_preview_mix_report()["url"] == report.as_uri()
    assert opened == [report.as_uri()]


def test_repeated_previews_are_isolated_and_export_preserves_active_result(
    tmp_path: Path,
) -> None:
    source = tmp_path / "voice.wav"
    sf.write(source, np.zeros(48_000 * 10, dtype=np.float32), 48_000, subtype="FLOAT")
    destinations: list[Path] = []

    class FakeEngine:
        @staticmethod
        def inspect(_paths):
            return _valid_preview_inspection(source)

        @staticmethod
        def preview(_paths, output, **_kwargs):
            destinations.append(output)
            rendered = output / "voice-preview.wav"
            report = output / "podcast-automix-report.json"
            html_report = output / "podcast-automix-report.html"
            rendered.write_bytes(b"audio")
            report.write_text("{}", encoding="utf-8")
            html_report.write_text("<html></html>", encoding="utf-8")
            return SimpleNamespace(outputs=[rendered], report=report, html_report=html_report)

    bridge = DesktopBridge(FakeEngine(), temp_directory=tmp_path / "temp")
    for start in (0.0, 1.0):
        bridge.start_preview([str(source)], start)
        while bridge.status()["state"] != "complete":
            sleep(0.01)

    active_before = bridge.status()["preview_result"]
    exported = bridge.export_preview(str(tmp_path / "exports"))

    assert destinations[0] != destinations[1]
    assert all(destination.parent == bridge._preview_session for destination in destinations)
    assert exported["state"] == "complete"
    export_directory = Path(exported["destination"])
    assert (export_directory / "voice-preview.wav").read_bytes() == b"audio"
    assert (export_directory / "podcast-automix-report.html").exists()
    assert bridge.status()["preview_result"] == active_before


def test_full_render_uses_a_unique_deliverable_folder_and_keeps_preview_separate(
    tmp_path: Path,
) -> None:
    source = tmp_path / "voice.wav"
    sf.write(source, np.zeros(48_000 * 10, dtype=np.float32), 48_000, subtype="FLOAT")
    default = tmp_path / "Podcast Automixer Output"
    default.mkdir()
    inspections: list[list[Path]] = []

    class FakeEngine:
        @staticmethod
        def inspect(paths):
            inspections.append(paths)
            return _valid_preview_inspection(source)

        @staticmethod
        def full_render(paths, destination, **kwargs):
            assert paths == [source]
            assert destination == tmp_path / "Podcast Automixer Output (2)"
            assert kwargs["confirm_overwrite"](1) is False
            output = destination / "voice-automixed.wav"
            output.touch()
            return SimpleNamespace(
                outputs=[output],
                report=destination / "report.json",
                html_report=destination / "report.html",
            )

    bridge = DesktopBridge(FakeEngine())
    result = bridge.start_full_render([str(source)])
    assert result == {
        "state": "running",
        "destination": str(tmp_path / "Podcast Automixer Output (2)"),
    }
    while bridge.status()["state"] != "complete":
        sleep(0.01)
    status = bridge.status()
    assert len(inspections) == 1
    assert status["full_render_result"]["outputs"] == [
        str(tmp_path / "Podcast Automixer Output (2)" / "voice-automixed.wav")
    ]
    assert "preview_result" not in status


def test_full_render_revalidates_and_playback_folder_failure_keeps_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "voice.wav"
    sf.write(source, np.zeros(48_000 * 10, dtype=np.float32), 48_000, subtype="FLOAT")

    class FakeEngine:
        @staticmethod
        def inspect(_paths):
            return SimpleNamespace(inputs=[], problems=[SimpleNamespace()])

    bridge = DesktopBridge(FakeEngine())
    with pytest.raises(ValueError, match="immediately before Full Render"):
        bridge.start_full_render([str(source)])

    bridge._last_full_render = {"destination": str(tmp_path), "outputs": []}
    monkeypatch.setattr(desktop.webbrowser, "open", lambda _url: (_ for _ in ()).throw(OSError()))
    monkeypatch.delattr(desktop.os, "startfile", raising=False)
    assert bridge.open_full_render_folder() == {"path": str(tmp_path)}
    assert bridge.status()["full_render_result"]["destination"] == str(tmp_path)


def test_cancelled_full_render_removes_its_new_empty_destination(tmp_path: Path) -> None:
    source = tmp_path / "voice.wav"
    sf.write(source, np.zeros(48_000 * 10, dtype=np.float32), 48_000, subtype="FLOAT")

    class FakeEngine:
        @staticmethod
        def inspect(_paths):
            return _valid_preview_inspection(source)

        @staticmethod
        def full_render(_paths, _destination, **_kwargs):
            raise desktop.AutomixCancelled()

    bridge = DesktopBridge(FakeEngine())
    bridge.start_full_render([str(source)])
    while bridge.status()["state"] != "cancelled":
        sleep(0.01)
    assert not (tmp_path / "Podcast Automixer Output").exists()


def test_full_render_report_acknowledgement_is_separate_from_render_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = tmp_path / "report.html"
    report.write_text("<html></html>", encoding="utf-8")
    bridge = DesktopBridge()
    bridge._last_full_render = {
        "destination": str(tmp_path),
        "outputs": [str(tmp_path / "mix.wav")],
        "html_report": str(report),
    }
    opened: list[str] = []
    monkeypatch.setattr(desktop.webbrowser, "open", opened.append)

    assert bridge.close_state() == {"active_processing": False, "unacknowledged_full_render": True}
    assert bridge.full_render_mix_report() == {"path": str(report), "url": report.as_uri()}
    assert bridge.close_state() == {"active_processing": False, "unacknowledged_full_render": False}
    assert bridge.open_full_render_mix_report()["url"] == report.as_uri()
    assert opened == [report.as_uri()]
