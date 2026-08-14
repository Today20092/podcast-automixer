import json
from pathlib import Path

import numpy as np
import soundfile as sf

from podcast_automixer.diagnostic_timeline import build_diagnostic_timeline


def test_builds_recording_set_timeline_with_shared_domain(tmp_path: Path) -> None:
    originals, rendered = [], []
    samples = np.sin(np.linspace(0, 80, 48_000, dtype=np.float32)) * 0.5
    for index in range(3):
        original, output = tmp_path / f"mic-{index}.wav", tmp_path / f"mic-{index}-automixed.wav"
        sf.write(original, samples, 48_000, subtype="FLOAT")
        sf.write(output, samples * 0.5, 48_000, subtype="FLOAT")
        originals.append(original)
        rendered.append(output)
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "settings": {"attenuation_db": -18},
                "diagnostic_timeline": {
                    "frame_ms": 100,
                    "speech_evidence": [[True, False]] * 3,
                    "automix_target": [[True, False]] * 3,
                    "applied_gain_db": [[0.0, -18.0]] * 3,
                },
            }
        ),
        encoding="utf-8",
    )

    result = build_diagnostic_timeline(originals, rendered, report, 0.0, 1.0)

    assert [lane["name"] for lane in result["lanes"]] == ["mic-0", "mic-1", "mic-2"]
    assert len({lane["color"] for lane in result["lanes"]}) == 3
    assert result["db_domain"] == {"minimum": -18.0, "maximum": 0.0}
    assert len(result["lanes"][0]["waveform_levels"]) > 1
