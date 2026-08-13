from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from podcast_automixer import cli
from podcast_automixer.core import AutomixError


def _payload(captured: pytest.CaptureFixture[str]) -> dict[str, object]:
    output = captured.readouterr()
    assert output.err == ""
    assert output.out.endswith("\n") and output.out.count("\n") == 1
    return json.loads(output.out)


def test_installed_command_returns_structured_argument_failure() -> None:
    command = shutil.which("podcast-automix")
    assert command
    completed = subprocess.run(
        [command, "--json", "--frame-ms", "nope"], capture_output=True, check=False
    )
    assert completed.returncode == 2
    assert completed.stderr == b""
    assert completed.stdout.endswith(b"\n")
    payload = json.loads(completed.stdout.decode("utf-8"))
    assert payload["error"]["code"] == "invalid_arguments"


@pytest.mark.parametrize("option", ["--help", "--version"])
def test_json_meta_options_do_not_escape_contract(option: str) -> None:
    command = shutil.which("podcast-automix")
    assert command
    completed = subprocess.run([command, "--json", option], capture_output=True, check=False)
    assert completed.returncode == 2
    assert completed.stderr == b""
    assert json.loads(completed.stdout)["error"]["code"] == "invalid_arguments"


def test_installed_command_returns_structured_configuration_failure(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text("schema_version = 2\n", encoding="utf-8")
    command = shutil.which("podcast-automix")
    assert command
    completed = subprocess.run(
        [command, "--json", "--config", path, "one.wav", "two.wav"],
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stderr == b""
    payload = json.loads(completed.stdout.decode("utf-8"))
    assert payload["error"]["code"] == "invalid_configuration"


def test_json_write_config_uses_contract_and_normalized_artifact(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    destination = tmp_path / "配置.toml"
    monkeypatch.setattr(
        "sys.argv", ["podcast-automix", "--json", "--write-config", str(destination)]
    )
    cli.main()
    payload = _payload(capfd)
    assert payload["status"] == "success"
    assert payload["run"] == {"kind": "configuration"}
    assert payload["artifacts"] == [str(destination.resolve())]
    assert set(payload) == {
        "schema_version", "cli_version", "status", "inputs", "run", "settings",
        "artifacts", "warnings", "error",
    }


@pytest.mark.parametrize(
    ("failure", "code", "exit_status"),
    [
        (AutomixError("File not found: missing.wav"), "invalid_inputs", 2),
        (AutomixError("2 artifact(s) already exist"), "output_collision", 2),
        (AutomixError("model failed"), "processing_failed", 2),
        (KeyboardInterrupt(), "cancelled", 130),
        (RuntimeError("unexpected"), "internal_failure", 1),
    ],
)
def test_json_run_failure_categories(
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    tmp_path: Path,
    failure: BaseException,
    code: str,
    exit_status: int,
) -> None:
    monkeypatch.setattr("sys.argv", ["podcast-automix", "--json", "one.wav", "two.wav"])

    def fail(*_args: object, **_kwargs: object) -> object:
        raise failure

    monkeypatch.setattr(cli, "run_automix", fail)
    with pytest.raises(SystemExit) as stopped:
        cli.main()
    assert stopped.value.code == exit_status
    payload = _payload(capfd)
    assert isinstance(payload["error"], dict)
    assert payload["error"]["code"] == code


def test_json_success_reports_ordered_normalized_paths_and_all_artifacts(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    inputs = [tmp_path / "一.wav", tmp_path / "二.wav"]
    outputs = [tmp_path / "一_auto-mixed.wav", tmp_path / "二_auto-mixed.wav"]
    result = SimpleNamespace(
        outputs=outputs,
        report=tmp_path / "report.json",
        html_report=tmp_path / "report.html",
        diagnostics=None,
    )
    monkeypatch.setattr(cli, "run_automix", lambda *_args, **_kwargs: result)
    monkeypatch.setattr("sys.argv", ["podcast-automix", "--json", *map(str, inputs)])
    cli.main()
    payload = _payload(capfd)
    assert payload["inputs"] == [str(path.resolve()) for path in inputs]
    assert payload["artifacts"] == [
        str(path.resolve()) for path in [*outputs, result.report, result.html_report]
    ]
    assert json.loads(json.dumps({**payload, "future_field": True}))["status"] == "success"


@pytest.mark.parametrize("name", ["success.json", "error.json"])
def test_contract_fixtures_have_stable_shape(name: str) -> None:
    payload = json.loads((Path(__file__).parent / "fixtures" / "automation" / name).read_text())
    assert set(payload) == {
        "schema_version", "cli_version", "status", "inputs", "run", "settings",
        "artifacts", "warnings", "error",
    }
    assert payload["schema_version"] == 1
