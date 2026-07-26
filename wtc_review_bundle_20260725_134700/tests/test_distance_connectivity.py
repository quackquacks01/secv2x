from __future__ import annotations

from simulation.sumo.controllers.run_wtc_sumo import (
    VehicleState,
    connectivity_link,
    euclidean_distance_m,
)


def state(vehicle_id: str, x_m: float, y_m: float) -> VehicleState:
    return VehicleState(
        vehicle_id=vehicle_id,
        simulation_time_ms=2_000,
        x_m=x_m,
        y_m=y_m,
        lane_position_m=x_m,
        speed_mps=13.89,
        acceleration_mps2=0.0,
        lane_id="E0_0",
        road_id="E0",
        route_edges=("E0",),
        route_index=0,
    )


def test_euclidean_distance_uses_sumo_xy_position():
    source = state("Vehicle-A", 200.0, 0.0)
    target = state("Witness-W1", 230.0, 4.0)

    assert euclidean_distance_m(source, target) == 30.265491900843113


def test_connectivity_range_accepts_near_and_rejects_far_witness():
    states = {
        "Vehicle-A": state("Vehicle-A", 200.0, 0.0),
        "Witness-W1": state("Witness-W1", 230.0, 0.0),
        "Witness-W5": state("Witness-W5", 290.0, 0.0),
    }

    near, near_distance = connectivity_link(
        "Vehicle-A",
        "Witness-W1",
        states,
        50.0,
    )
    far, far_distance = connectivity_link(
        "Vehicle-A",
        "Witness-W5",
        states,
        50.0,
    )

    assert near is True
    assert near_distance == 30.0
    assert far is False
    assert far_distance == 90.0


def test_unlimited_range_preserves_backward_compatibility():
    states = {
        "Vehicle-A": state("Vehicle-A", 0.0, 0.0),
    }

    connected, distance = connectivity_link(
        "Vehicle-A",
        "missing-witness",
        states,
        None,
    )

    assert connected is True
    assert distance is None
