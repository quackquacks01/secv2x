from __future__ import annotations

import json
from pathlib import Path

from simulation.experiments.run_sweep import build_cases, load_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_pilot_config_builds_expected_number_of_cases():
    path = (
        PROJECT_ROOT
        / "simulation"
        / "experiments"
        / "configs"
        / "pilot.json"
    )
    config = load_config(path)
    cases = build_cases(config)

    assert len(cases) == 24
    assert {case["algorithm"] for case in cases} == {"mock"}
    assert {case["vehicle_count"] for case in cases} == {3, 10}
    assert {case["delay_ms"] for case in cases} == {0, 50}
    assert {case["loss_rate"] for case in cases} == {0.0, 0.05}
