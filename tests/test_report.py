import json
from pathlib import Path
from typing import Any

import numpy as np

from podcast_automixer.core import AudioInfo, Settings
from podcast_automixer.report import Report


def _shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _shape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_shape(value[0])] if value else []
    if value is None:
        return None
    return type(value)


def test_html_payload_matches_report_ui_contract() -> None:
    infos = [
        AudioInfo(Path(f"A0{index}.wav"), 48_000, 1, 96_000, "FLOAT", "WAV")
        for index in range(1, 4)
    ]
    gains = np.array([[1.0, 0.5], [1.0, 1.0], [0.5, 0.5]], dtype=np.float32)
    active = np.array([[True, False], [False, True], [False, False]])
    analysis = {
        "calibration_db": [0.0, 0.0, 0.0],
        "noise_floor_db": [-60.0, -60.0, -60.0],
        "active_percent": [50.0, 50.0, 0.0],
    }
    produced = Report(infos, Settings(frame_ms=1000), gains, active, analysis).html_payload()
    contract_path = Path(__file__).parents[1] / "report-ui" / "report-contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    assert _shape(produced) == _shape(contract)


def test_report_owns_shared_gain_calculation() -> None:
    gains = np.array([[1.0], [0.5], [1e-10]], dtype=np.float32)
    report = Report([], Settings(), gains, np.zeros((3, 1), dtype=bool), {})

    assert report.gain_db[:, 0].tolist() == [0.0, -6.020600318908691, -180.0]
    assert report.diagnostics_rows()[0][-3:] == ["0.000", "-6.021", "-180.000"]
    assert report.json_payload()["gain_reduction_db"]["minimum"] == [
        0.0,
        -6.020600318908691,
        -180.0,
    ]
