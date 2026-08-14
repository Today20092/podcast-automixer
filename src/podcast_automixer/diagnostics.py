"""Fail-open, privacy-preserving diagnostics for the desktop application."""

from __future__ import annotations

import logging
import os
import re
import tempfile
import traceback
from contextlib import suppress
from logging.handlers import RotatingFileHandler
from pathlib import Path
from uuid import uuid4

_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|/)[^\r\n\t<>\"']*?(?P<name>[^\\/\r\n\t<>\"']+\.[A-Za-z0-9]{1,10})"
)


def redact_paths(value: object) -> str:
    """Keep filenames useful while excluding recording and destination directories."""
    return _PATH.sub(lambda match: f"<redacted>/{match.group('name')}", str(value))


def diagnostics_directory() -> Path:
    """Return the documented per-user log directory without creating it."""
    base = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
    return base / "Podcast Automixer" / "Logs"


class DesktopDiagnostics:
    """Best-effort rotating session logging; no logging error may affect audio work."""

    def __init__(self, directory: Path | None = None, version: str = "unknown") -> None:
        self.directory = directory or diagnostics_directory()
        self.session_id = uuid4().hex[:12]
        self.logger = logging.getLogger(f"podcast_automixer.desktop.{self.session_id}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                self.directory / "desktop.log", maxBytes=1_000_000, backupCount=6, encoding="utf-8"
            )
            handler.setFormatter(logging.Formatter("%(asctime)sZ %(levelname)s %(message)s"))
            self.logger.addHandler(handler)
            self.log("session_start version=%s session=%s", version, self.session_id)
        except Exception:
            self.logger.disabled = True

    def log(self, message: str, *args: object, level: int = logging.INFO) -> None:
        with suppress(Exception):
            self.logger.log(level, redact_paths(message % args))

    def exception(self, operation: str, exc: BaseException) -> None:
        self.log(
            "operation_failed operation=%s error=%s traceback=%s",
            operation,
            exc,
            "".join(traceback.format_exception(exc)),
            level=logging.ERROR,
        )
