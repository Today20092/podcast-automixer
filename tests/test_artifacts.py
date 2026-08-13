import struct
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from podcast_automixer.artifacts import RenderedAudioArtifacts
from podcast_automixer.core import AutomixError, Settings, inspect_inputs


def _add_bext(path: Path, time_reference: int) -> None:
    payload = bytearray(602)
    struct.pack_into("<Q", payload, 338, time_reference)
    raw = path.read_bytes()
    data_at = raw.index(b"data")
    rebuilt = raw[:data_at] + struct.pack("<4sI", b"bext", len(payload)) + payload + raw[data_at:]
    path.write_bytes(rebuilt[:4] + struct.pack("<I", len(rebuilt) - 8) + rebuilt[8:])


def _riff_chunk(path: Path, wanted: bytes) -> bytes | None:
    with path.open("rb") as stream:
        stream.seek(12)
        while header := stream.read(8):
            chunk_id, size = struct.unpack("<4sI", header)
            payload = stream.read(size)
            if chunk_id == wanted:
                return payload
            if size % 2:
                stream.seek(1, 1)
    return None


def _inputs(tmp_path: Path) -> list[Path]:
    paths = [tmp_path / f"track-{index}.wav" for index in range(3)]
    audio = np.linspace(-0.5, 0.5, 40, dtype=np.float32)
    for path in paths:
        sf.write(path, audio, 100, format="WAVEX", subtype="FLOAT")
        _add_bext(path, 1_000)
    return paths


def test_rendered_artifacts_preserve_audio_structure_metadata_and_preview_offset(
    tmp_path: Path,
) -> None:
    paths = _inputs(tmp_path)
    artifacts = RenderedAudioArtifacts.prepare(inspect_inputs(paths), preview=True, overwrite=False)

    outputs = artifacts.render(np.full((3, 2), 0.5), Settings(frame_ms=100), 10, 20)

    assert [path.name for path in outputs] == [
        f"track-{index}_auto-mixed-preview.wav" for index in range(3)
    ]
    for source, output in zip(paths, outputs, strict=True):
        info = sf.info(output)
        assert (info.format, info.subtype, info.samplerate, info.channels, info.frames) == (
            "WAVEX",
            "FLOAT",
            100,
            1,
            20,
        )
        expected = sf.read(source, dtype="float32")[0][10:30] * 0.5
        assert sf.read(output, dtype="float32")[0] == pytest.approx(expected, abs=1e-7)
        bext = _riff_chunk(output, b"bext")
        assert bext is not None
        assert struct.unpack_from("<Q", bext, 338)[0] == 1_010


def test_collision_policy_is_owned_by_rendered_artifacts(tmp_path: Path) -> None:
    infos = inspect_inputs(_inputs(tmp_path))
    collision = tmp_path / "track-0_auto-mixed.wav"
    collision.write_bytes(b"existing")
    confirmations: list[int] = []

    with pytest.raises(AutomixError, match="Cancelled"):
        RenderedAudioArtifacts.prepare(
            infos,
            preview=False,
            overwrite=False,
            confirm_overwrite=lambda count: confirmations.append(count) or False,
        )

    assert confirmations == [1]
    assert collision.read_bytes() == b"existing"


def test_collision_policy_includes_non_audio_artifacts(tmp_path: Path) -> None:
    infos = inspect_inputs(_inputs(tmp_path))
    report = tmp_path / "podcast-automix-report.json"
    report.write_bytes(b"existing")

    with pytest.raises(AutomixError, match="Cancelled"):
        RenderedAudioArtifacts.prepare(
            infos,
            preview=False,
            overwrite=False,
            additional_artifacts=(report.name,),
        )

    assert report.read_bytes() == b"existing"


def test_failed_render_preserves_destination_and_removes_temporary_file(
    tmp_path: Path,
) -> None:
    infos = inspect_inputs(_inputs(tmp_path))
    destination = tmp_path / "track-0_auto-mixed.wav"
    destination.write_bytes(b"existing")
    artifacts = RenderedAudioArtifacts.prepare(infos, preview=False, overwrite=True)

    def fail(*_args) -> None:
        raise OSError("render failed")

    with pytest.raises(OSError, match="render failed"):
        artifacts.render(np.ones((3, 2)), Settings(frame_ms=100), 0, 20, progress=fail)

    assert destination.read_bytes() == b"existing"
    assert not list(tmp_path.glob(".*-*.wav"))
