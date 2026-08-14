from __future__ import annotations

import math
import os
import tempfile
import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .core import Settings

MAX_CONFIG_BYTES = 64 * 1024
FIELDS = tuple(asdict(Settings()))
INT_FIELDS = {"frame_ms", "preroll_ms", "hold_ms", "segment_seconds"}
NONNEGATIVE_FIELDS = {"ambiguity_db", "preroll_ms", "hold_ms"}


def load_configuration(path: Path) -> dict[str, int | float]:
    if path.stat().st_size > MAX_CONFIG_BYTES:
        raise ValueError(f"Configuration exceeds {MAX_CONFIG_BYTES} bytes: {path}")
    try:
        with path.open("rb") as source:
            document = tomllib.load(source)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Invalid configuration TOML: {exc}") from exc

    errors: list[str] = []
    unknown_root = sorted(set(document) - {"schema_version", "settings"})
    if unknown_root:
        errors.append(f"unknown top-level key(s): {', '.join(unknown_root)}")
    if document.get("schema_version") != 1 or isinstance(document.get("schema_version"), bool):
        errors.append("schema_version must be integer 1")
    raw = document.get("settings")
    if not isinstance(raw, dict):
        errors.append("settings must be one table")
        raw = {}
    unknown_settings = sorted(set(raw) - set(FIELDS))
    if unknown_settings:
        errors.append(f"unknown settings key(s): {', '.join(unknown_settings)}")

    values: dict[str, int | float] = {}
    for name in FIELDS:
        if name not in raw:
            continue
        value = raw[name]
        expected = int if name in INT_FIELDS else (int, float)
        if isinstance(value, bool) or not isinstance(value, expected):
            errors.append(f"settings.{name} has the wrong scalar type")
            continue
        if isinstance(value, float) and not math.isfinite(value):
            errors.append(f"settings.{name} must be finite")
            continue
        if name == "attenuation_db" and value > 0:
            errors.append("settings.attenuation_db must be zero or less")
        elif name in NONNEGATIVE_FIELDS and value < 0:
            errors.append(f"settings.{name} must be zero or greater")
        elif name not in NONNEGATIVE_FIELDS | {"attenuation_db"} and value <= 0:
            errors.append(f"settings.{name} must be greater than zero")
        else:
            values[name] = value
    if errors:
        raise ValueError("Invalid configuration:\n- " + "\n- ".join(errors))
    return values


def resolve_settings(args: Any) -> Settings:
    values = asdict(Settings())
    if args.config:
        values.update(load_configuration(args.config))
    for field, option in {
        "attenuation_db": "attenuation",
        "frame_ms": "frame_ms",
        "ambiguity_db": "ambiguity",
        "preroll_ms": "preroll_ms",
        "hold_ms": "hold_ms",
        "open_ms": "open_ms",
        "close_ms": "close_ms",
        "segment_seconds": "segment_seconds",
    }.items():
        if (value := getattr(args, option)) is not None:
            values[field] = value
    return Settings(**values)


def write_configuration(path: Path, settings: Settings, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ValueError(f"Configuration already exists; rerun with --overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    values = asdict(settings)
    content = "schema_version = 1\n\n[settings]\n" + "".join(
        f"{name} = {values[name]}\n" for name in FIELDS
    )
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as output:
            temporary = output.name
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
