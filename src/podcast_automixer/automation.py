"""Versioned JSON contract for command-line automation."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any

from .core import Settings

SCHEMA_VERSION = 1


def result(
    *,
    status: str,
    inputs: list[Path] | None = None,
    kind: str = "automix",
    settings: Settings | None = None,
    artifacts: list[Path] | None = None,
    error: tuple[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "cli_version": version("podcast-automixer"),
        "status": status,
        "inputs": [str(path.resolve()) for path in inputs or []],
        "run": {"kind": kind},
        "settings": asdict(settings) if settings else {},
        "artifacts": [str(path.resolve()) for path in artifacts or []],
        "warnings": [],
        "error": {"code": error[0], "message": error[1]} if error else None,
    }


def write(payload: dict[str, Any]) -> None:
    """Write exactly one strict UTF-8 JSON object and newline."""
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    data = (text + "\n").encode("utf-8")
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()
