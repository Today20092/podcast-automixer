from pathlib import Path
from types import SimpleNamespace

import pytest

from podcast_automixer.configuration import (
    MAX_CONFIG_BYTES,
    load_configuration,
    resolve_settings,
    write_configuration,
)
from podcast_automixer.core import Settings


def _args(**overrides: object) -> SimpleNamespace:
    values = {
        "config": None,
        "attenuation": None,
        "frame_ms": None,
        "ambiguity": None,
        "preroll_ms": None,
        "hold_ms": None,
        "open_ms": None,
        "close_ms": None,
        "segment_seconds": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_configuration_precedence_and_unicode_path(tmp_path: Path) -> None:
    path = tmp_path / "mix café.toml"
    path.write_text(
        "schema_version = 1\n[settings]\nattenuation_db = -12.0\nframe_ms = 10\n",
        encoding="utf-8",
    )

    settings = resolve_settings(_args(config=path, attenuation=-8.0))

    assert settings == Settings(attenuation_db=-8.0, frame_ms=10)


def test_configuration_accumulates_validation_errors(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(
        "schema_version = 2\nextra = true\n[settings]\nframe_ms = 'fast'\nopen_ms = -1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as failure:
        load_configuration(path)

    message = str(failure.value)
    assert "schema_version" in message
    assert "unknown top-level key(s): extra" in message
    assert "settings.frame_ms has the wrong scalar type" in message
    assert "settings.open_ms must be greater than zero" in message


def test_configuration_rejects_duplicate_and_oversized_input(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.toml"
    duplicate.write_text(
        "schema_version = 1\n[settings]\nframe_ms = 10\nframe_ms = 20\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Cannot overwrite a value"):
        load_configuration(duplicate)

    oversized = tmp_path / "large.toml"
    oversized.write_bytes(b" " * (MAX_CONFIG_BYTES + 1))
    with pytest.raises(ValueError, match="exceeds"):
        load_configuration(oversized)


def test_configuration_write_is_deterministic_and_protects_existing_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nested" / "settings.toml"
    write_configuration(path, Settings(), overwrite=False)
    original = path.read_bytes()

    assert original.startswith(b"schema_version = 1\n\n[settings]\n")
    assert load_configuration(path) == {
        "attenuation_db": -6.0,
        "frame_ms": 20,
        "ambiguity_db": 9.0,
        "preroll_ms": 150,
        "hold_ms": 400,
        "open_ms": 50.0,
        "close_ms": 500.0,
        "segment_seconds": 30,
    }
    with pytest.raises(ValueError, match="--overwrite"):
        write_configuration(path, Settings(frame_ms=10), overwrite=False)
    assert path.read_bytes() == original

    write_configuration(path, Settings(frame_ms=10), overwrite=True)
    assert load_configuration(path)["frame_ms"] == 10
