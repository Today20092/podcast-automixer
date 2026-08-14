"""Smoke-test the installed wheel's public console-script contract."""

from __future__ import annotations

import json
import math
import struct
import subprocess
import tempfile
import wave
from pathlib import Path


def run(*args: object, expected: int = 0) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["podcast-automix", *(str(arg) for arg in args)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == expected, completed.stderr or completed.stdout
    return completed


def write_tone(path: Path, frequency: float) -> None:
    rate = 16_000
    samples = (
        int(4_000 * math.sin(2 * math.pi * frequency * index / rate)) for index in range(rate)
    )
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, rate, rate, "NONE", "not compressed"))
        output.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))


def main() -> None:
    assert "usage:" in run("--help").stdout.lower()
    assert run("--version").stdout.strip().endswith("0.2.0")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        config = root / "automix.toml"
        assert json.loads(run("--json", "--write-config", config).stdout)["status"] == "success"
        assert (
            json.loads(run("--json", "--frame-ms", "nope", expected=2).stdout)["error"]["code"]
            == "invalid_arguments"
        )
        inputs = [root / "host.wav", root / "guest.wav"]
        write_tone(inputs[0], 220)
        write_tone(inputs[1], 440)
        output = root / "out"
        output.mkdir()
        payload = json.loads(run("--json", "--output-dir", output, *inputs).stdout)
        assert payload["status"] == "success" and payload["artifacts"]


if __name__ == "__main__":
    main()
