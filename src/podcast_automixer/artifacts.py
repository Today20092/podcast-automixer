from __future__ import annotations

import os
import struct
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from .core import AudioInfo, AutomixError, ProgressCallback, Settings

OverwriteConfirmation = Callable[[int], bool]


@dataclass(frozen=True)
class RenderedAudioArtifacts:
    """Destination policy and atomic creation of one run's rendered WAV artifacts."""

    infos: list[AudioInfo]
    paths: list[Path]

    @classmethod
    def prepare(
        cls,
        infos: list[AudioInfo],
        *,
        preview: bool,
        overwrite: bool,
        confirm_overwrite: OverwriteConfirmation | None = None,
    ) -> RenderedAudioArtifacts:
        suffix = "_auto-mixed-preview.wav" if preview else "_auto-mixed.wav"
        paths = [info.path.with_name(f"{info.path.stem}{suffix}") for info in infos]
        collisions = [path for path in paths if path.exists()]
        if collisions and not overwrite:
            confirmed = bool(confirm_overwrite and confirm_overwrite(len(collisions)))
            if not confirmed:
                raise AutomixError("Cancelled; no output files were changed.")
        return cls(infos, paths)

    def render(
        self,
        gains: np.ndarray,
        settings: Settings,
        start_frame: int,
        frame_count: int,
        progress: ProgressCallback | None = None,
    ) -> list[Path]:
        samplerate = self.infos[0].samplerate
        samples_per_frame = round(samplerate * settings.frame_ms / 1000)
        chunk = samplerate * 30
        for channel, (info, destination) in enumerate(zip(self.infos, self.paths, strict=True)):
            temporary = _temporary_wav(destination)
            try:
                with (
                    sf.SoundFile(info.path) as source,
                    sf.SoundFile(
                        temporary,
                        mode="w",
                        samplerate=samplerate,
                        channels=1,
                        format=info.format,
                        subtype=info.subtype,
                    ) as target,
                ):
                    source.seek(start_frame)
                    offset = 0
                    remaining = frame_count
                    while remaining:
                        wanted = min(remaining, chunk)
                        audio = source.read(wanted, dtype="float32", always_2d=False)
                        sample_positions = (offset + np.arange(len(audio))) / samples_per_frame
                        gain = np.interp(
                            sample_positions, np.arange(gains.shape[1]), gains[channel]
                        )
                        target.write((audio * gain).astype(np.float32))
                        offset += len(audio)
                        remaining -= len(audio)
                        if progress:
                            progress(
                                "Rendering",
                                channel + 1,
                                channel * frame_count + offset,
                                3 * frame_count,
                            )
                _preserve_bext(info.path, temporary, start_frame)
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
                temporary.with_suffix(".bwf-tmp.wav").unlink(missing_ok=True)
        return self.paths


def _temporary_wav(destination: Path) -> Path:
    with tempfile.NamedTemporaryFile(
        dir=destination.parent, prefix=f".{destination.stem}-", suffix=".wav", delete=False
    ) as stream:
        return Path(stream.name)


def _read_riff_chunk(path: Path, wanted: bytes) -> bytes | None:
    with path.open("rb") as stream:
        if stream.read(4) not in {b"RIFF", b"RF64"}:
            return None
        stream.seek(12)
        while header := stream.read(8):
            chunk_id, size = struct.unpack("<4sI", header)
            payload = stream.read(size)
            if chunk_id == wanted:
                return payload
            if size % 2:
                stream.seek(1, os.SEEK_CUR)
    return None


def _preserve_bext(source: Path, destination: Path, sample_offset: int) -> None:
    bext = _read_riff_chunk(source, b"bext")
    if bext is None:
        return
    if len(bext) >= 346:
        mutable = bytearray(bext)
        original_reference = struct.unpack_from("<Q", mutable, 338)[0]
        struct.pack_into("<Q", mutable, 338, original_reference + sample_offset)
        bext = bytes(mutable)
    rewritten = destination.with_suffix(".bwf-tmp.wav")
    with destination.open("rb") as incoming, rewritten.open("wb") as outgoing:
        outgoing.write(incoming.read(12))
        inserted = False
        while chunk_header := incoming.read(8):
            chunk_id, size = struct.unpack("<4sI", chunk_header)
            if chunk_id == b"bext":
                incoming.seek(size + size % 2, os.SEEK_CUR)
                continue
            if chunk_id == b"data" and not inserted:
                outgoing.write(struct.pack("<4sI", b"bext", len(bext)))
                outgoing.write(bext)
                if len(bext) % 2:
                    outgoing.write(b"\0")
                inserted = True
            outgoing.write(chunk_header)
            remaining = size + size % 2
            while remaining:
                block = incoming.read(min(1024 * 1024, remaining))
                if not block:
                    raise AutomixError(f"Unexpected end of WAV file: {destination}")
                outgoing.write(block)
                remaining -= len(block)
        file_size = outgoing.tell()
        outgoing.seek(4)
        outgoing.write(struct.pack("<I", file_size - 8))
    rewritten.replace(destination)
