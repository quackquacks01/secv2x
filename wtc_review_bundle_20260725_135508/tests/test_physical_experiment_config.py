from __future__ import annotations

from pathlib import Path

from simulation.experiments.run_sweep import build_cases, load_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_physical_scaling_smoke_case_count_and_ranges():
    config = load_config(
        PROJECT_ROOT
        / "simulation"
        / "experiments"
        / "configs"
        / "physical_scaling_smoke.json"
    )
    cases = build_cases(config)

    assert len(cases) == 72
    assert {case["vehicle_count"] for case in cases} == {10, 50, 100}
    assert {case["witness_count"] for case in cases} == {5}
    assert {
        case["communication_range_m"]
        for case in cases
    } == {50, 120}
