from pathlib import Path

import pytest

from podcast_automixer.engine import (
    AutomixCancelled,
    AutomixEngine,
    AutomixEventName,
    CancellationToken,
)
from podcast_automixer.run import RunResult


def test_inspection_returns_structured_problem_for_invalid_recording_set(tmp_path: Path) -> None:
    inspection = AutomixEngine().inspect([tmp_path / "missing.wav"])

    assert inspection.inputs == []
    assert inspection.problems[0].code == "invalid_recording_set"
    assert "File not found" in inspection.problems[0].message


def test_inspection_returns_structured_problem_for_unreadable_wav(tmp_path: Path) -> None:
    unreadable = tmp_path / "corrupt.wav"
    unreadable.write_bytes(b"not audio")

    inspection = AutomixEngine().inspect([unreadable])

    assert inspection.inputs == []
    assert inspection.problems[0].code == "invalid_recording_set"


def test_preview_uses_explicit_destination_and_stable_progress(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "source.wav"
    destination = tmp_path / "preview"
    events = []

    def fake_run(request, **kwargs):
        assert request.output_directory == destination
        assert request.preview_start == 2.0
        kwargs["progress"]("Analyzing", 1, 2, 3)
        return RunResult([], destination / "report.json", destination / "report.html", None)

    AutomixEngine(fake_run).preview(
        [source], destination, start_seconds=2.0, progress=events.append
    )

    assert events[0].name is AutomixEventName.ANALYZING


def test_full_render_honors_cooperative_cancellation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    token = CancellationToken()

    def fake_run(_request, **kwargs):
        token.cancel()
        kwargs["check_cancelled"]()

    with pytest.raises(AutomixCancelled):
        AutomixEngine(fake_run).full_render([tmp_path / "source.wav"], tmp_path, cancellation=token)
