from pathlib import Path
from time import monotonic, sleep
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

import podcast_automixer.desktop as desktop
from podcast_automixer.desktop import DesktopBridge, _dialog_path, _dropped_file_paths
from podcast_automixer.engine import AutomixEngine


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


def test_preview_cleanup_removes_only_temporary_preview_artifacts(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    full_render = tmp_path / "Podcast Automixer Output" / "complete.wav"
    temporary = tmp_path / "Preview Runs" / "incomplete.bwf-tmp.wav"
    completed_preview = tmp_path / "Preview Runs" / "complete-preview.wav"
    source.write_bytes(b"source")
    full_render.parent.mkdir()
    full_render.write_bytes(b"render")
    temporary.parent.mkdir()
    temporary.write_bytes(b"temporary")
    completed_preview.write_bytes(b"preview")

    bridge = DesktopBridge()

    assert bridge.abandoned_preview_runs(str(tmp_path)) == {"paths": [str(temporary)]}
    assert bridge.remove_abandoned_preview_runs(str(tmp_path)) == {"paths": [str(temporary)]}
    assert source.exists()
    assert full_render.exists()
    assert completed_preview.exists()
    assert not temporary.exists()


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
        assert _output == tmp_path / "Preview Runs"
        while True:
            kwargs["cancellation"].raise_if_cancelled()
            sleep(0.01)

    class FakeEngine:
        @staticmethod
        def inspect(_paths):
            return AutomixEngine().inspect([source])

        preview = staticmethod(fake_preview)

    source = tmp_path / "voice.wav"
    sf.write(source, np.zeros(48_000 * 40, dtype=np.float32), 48_000, subtype="FLOAT")
    bridge = DesktopBridge(FakeEngine())
    bridge._last_success = {"outputs": ["previous-preview.wav"]}
    result = bridge.start_preview([str(source)], str(tmp_path), 2.0, 30.0)
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
            return AutomixEngine().inspect([source])

        @staticmethod
        def preview(_paths, _output, **kwargs):
            assert kwargs["start_seconds"] == 3.0
            assert kwargs["duration_seconds"] == 5.0
            kwargs["cancellation"].raise_if_cancelled()
            return SimpleNamespace(
                outputs=[], report=tmp_path / "report.json", html_report=tmp_path / "report.html"
            )

    bridge = DesktopBridge(FakeEngine())
    result = bridge.start_preview([str(source)], str(tmp_path), 7.0, 30.0)
    assert result["start_seconds"] == 3.0
    assert result["duration_seconds"] == 5.0
    while bridge.status()["state"] != "complete":
        sleep(0.01)


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
            return AutomixEngine().inspect([source])

        @staticmethod
        def preview(_paths, _output, **kwargs):
            if kwargs["start_seconds"]:
                raise RuntimeError("disk is unavailable")
            return SimpleNamespace(
                outputs=[rendered], report=tmp_path / "report.json", html_report=report
            )

    bridge = DesktopBridge(FakeEngine())
    bridge.start_preview([str(source)], str(tmp_path))
    while bridge.status()["state"] != "complete":
        sleep(0.01)
    bridge.start_preview([str(source)], str(tmp_path), 1.0)
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
            return AutomixEngine().inspect([source])

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
            return AutomixEngine().inspect([source])

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
