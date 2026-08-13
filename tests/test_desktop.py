from pathlib import Path
from time import monotonic, sleep
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

import podcast_automixer.desktop as desktop
from podcast_automixer.desktop import DesktopBridge
from podcast_automixer.engine import AutomixEngine


def test_bridge_validates_only_wav_family_recording_sets() -> None:
    with pytest.raises(ValueError, match="WAV-family"):
        DesktopBridge(AutomixEngine()).inspect_recording_set(["voice.mp3"])


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
        "paths": [str(original)], "outputs": [str(rendered)],
        "start_seconds": 0.0, "duration_seconds": 1.0,
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
