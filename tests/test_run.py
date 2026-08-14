from pathlib import Path

import numpy as np
import pytest

from podcast_automixer import run
from podcast_automixer.core import AnalysisResult, AudioInfo, AutomixError, Settings


def _infos(tmp_path: Path) -> list[AudioInfo]:
    return [
        AudioInfo(tmp_path / f"track-{index}.wav", 100, 1, 1_000, "PCM_16", "WAV")
        for index in range(3)
    ]


def _stub_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[AudioInfo]:
    infos = _infos(tmp_path)
    monkeypatch.setattr(run, "inspect_inputs", lambda _paths: infos)
    gains = np.ones((3, 10), dtype=np.float32)
    active = np.ones((3, 10), dtype=bool)
    analysis = AnalysisResult(gains, active, np.zeros(3), np.zeros(3), 20, 0, 1_000, 2)
    monkeypatch.setattr(run, "analyze", lambda *_args, **_kwargs: analysis)

    class StubArtifacts:
        def __init__(self, preview: bool) -> None:
            suffix = "_auto-mixed-preview.wav" if preview else "-automixed.wav"
            self.paths = [info.path.with_name(f"{info.path.stem}{suffix}") for info in infos]

        def render(self, *_args, **_kwargs):
            for output in self.paths:
                output.touch()
            return self.paths

    monkeypatch.setattr(
        run.RenderedAudioArtifacts,
        "prepare",
        lambda _infos, *, preview, **_kwargs: StubArtifacts(preview),
    )
    monkeypatch.setattr(run, "analyze_rendered_loudness", lambda _outputs, **_kwargs: {})
    monkeypatch.setattr(run, "write_json_report", lambda destination, *_args: destination.touch())
    monkeypatch.setattr(run, "write_html_report", lambda destination, *_args: destination.touch())
    return infos


@pytest.mark.parametrize(
    ("preview_start", "expected_suffix"),
    [(None, "-automixed.wav"), (2.0, "_auto-mixed-preview.wav")],
)
def test_run_completes_full_and_preview_runs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    preview_start: float | None,
    expected_suffix: str,
) -> None:
    infos = _stub_pipeline(monkeypatch, tmp_path)

    result = run.run_automix(
        run.RunRequest([info.path for info in infos], Settings(), preview_start=preview_start)
    )

    assert all(path.name.endswith(expected_suffix) for path in result.outputs)
    assert result.report.name == "podcast-automix-report.json"
    assert result.html_report.name == "podcast-automix-report.html"


def test_run_refuses_overwrite_before_analysis(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    infos = _infos(tmp_path)
    collision = infos[0].path.with_name(f"{infos[0].path.stem}-automixed.wav")
    collision.touch()
    monkeypatch.setattr(run, "inspect_inputs", lambda _paths: infos)
    monkeypatch.setattr(
        run, "analyze", lambda *_args, **_kwargs: pytest.fail("analysis should not start")
    )

    with pytest.raises(AutomixError, match="Cancelled"):
        run.run_automix(
            run.RunRequest([info.path for info in infos], Settings()),
            confirm_overwrite=lambda count: False,
        )

    assert collision.exists()


def test_run_removes_new_artifacts_after_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    infos = _stub_pipeline(monkeypatch, tmp_path)

    def fail_report(*_args) -> None:
        raise OSError("report failed")

    monkeypatch.setattr(run, "write_json_report", fail_report)

    with pytest.raises(OSError, match="report failed"):
        run.run_automix(run.RunRequest([info.path for info in infos], Settings()))

    assert not list(tmp_path.glob("*auto-mixed*"))
    assert not list(tmp_path.glob("podcast-automix-report.*"))


def test_run_removes_new_artifacts_when_loudness_measurement_is_cancelled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    infos = _stub_pipeline(monkeypatch, tmp_path)

    def cancel_loudness(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(run, "analyze_rendered_loudness", cancel_loudness)

    with pytest.raises(KeyboardInterrupt):
        run.run_automix(run.RunRequest([info.path for info in infos], Settings()))

    assert not list(tmp_path.glob("*auto-mixed*"))
    assert not list(tmp_path.glob("podcast-automix-report.*"))
