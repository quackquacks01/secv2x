from __future__ import annotations

from collections import defaultdict

from simulation.sumo.generators.generate_scalable_scenario import (
    build_vehicle_specs,
    minimum_safe_background_spacing_m,
)


def test_default_n100_layout_has_safe_same_lane_spacing():
    specs = build_vehicle_specs(
        vehicle_count=100,
        witness_count=5,
        lane_count=4,
        speed_mps=13.89,
    )

    background = [
        spec
        for spec in specs
        if spec.role == "BACKGROUND"
    ]
    by_lane = defaultdict(list)
    for spec in background:
        by_lane[spec.lane_index].append(spec.depart_position_m)

    minimum_expected = minimum_safe_background_spacing_m(13.89)
    assert minimum_expected == 30.0

    for positions in by_lane.values():
        positions = sorted(positions)
        gaps = [
            later - earlier
            for earlier, later in zip(positions, positions[1:])
        ]
        assert gaps
        assert min(gaps) >= minimum_expected


def test_requested_too_small_spacing_is_raised_to_safe_value():
    specs = build_vehicle_specs(
        vehicle_count=100,
        witness_count=5,
        lane_count=4,
        background_spacing_m=15.0,
        speed_mps=13.89,
    )

    lane_zero_positions = sorted(
        spec.depart_position_m
        for spec in specs
        if spec.role == "BACKGROUND" and spec.lane_index == 0
    )
    gaps = [
        later - earlier
        for earlier, later in zip(
            lane_zero_positions,
            lane_zero_positions[1:],
        )
    ]
    assert min(gaps) >= 30.0
