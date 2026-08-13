import json
from pathlib import Path

import numpy as np
import soundfile as sf

from podcast_automixer.diagnostic_timeline import build_diagnostic_timeline


def test_builds_multiresolution_one_microphone_timeline(tmp_path: Path) -> None:
    original = tmp_path / "mic.wav"
    rendered = tmp_path / "mic-automixed.wav"
    report = tmp_path / "report.json"
    samples = np.sin(np.linspace(0, 80, 48_000, dtype=np.float32)) * 0.5
    sf.write(original, samples, 48_000, subtype="FLOAT")
    sf.write(rendered, samples * 0.5, 48_000, subtype="FLOAT")
    report.write_text(
        json.dumps(
            {
                "diagnostic_timeline": {
                    "frame_ms": 100,
                    "speech_evidence": [[True, False]],
                    "automix_target": [[True, False]],
                    "applied_gain_db": [[0.0, -6.0]],
                }
            }
        ),
        encoding="utf-8",
    )

    result = build_diagnostic_timeline(original, rendered, report, 0.0, 1.0)

    assert len(result["waveform_levels"]) > 1
    assert max(result["waveform_levels"][0][0]) > max(result["gain_adjusted_waveform_levels"][0][0])
    assert result["speech_evidence"] == [True, False]
    assert result["applied_gain_db"] == [0.0, -6.0]
