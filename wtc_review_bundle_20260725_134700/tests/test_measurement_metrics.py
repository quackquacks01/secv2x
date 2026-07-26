from __future__ import annotations

from simulation.experiments.run_sweep import flatten_result, summarize
from simulation.sumo.controllers.run_wtc_sumo import VehicleState


def test_vehicle_state_keeps_route_information():
    state = VehicleState(
        vehicle_id="Vehicle-A",
        simulation_time_ms=1000,
        x_m=1.0,
        y_m=2.0,
        lane_position_m=3.0,
        speed_mps=4.0,
        acceleration_mps2=0.0,
        lane_id="E0_0",
        road_id="E0",
        route_edges=("E0", "E1"),
        route_index=0,
    )
    payload = state.to_dict()
    assert payload["route_edges"] == ("E0", "E1")
    assert payload["route_index"] == 0


def test_sweep_uses_simulated_and_wall_metrics_separately():
    result = {
        "run_id": "x",
        "status": "PASS",
        "scenario": "equivocation",
        "algorithm": "haetae",
        "seed": 1,
        "requested_vehicle_count": 3,
        "observed_sumo_vehicle_count": 3,
        "witness_count": 2,
        "slot_count": 5,
        "delay_ms": 50,
        "jitter_ms": 0,
        "loss_rate": 0.0,
        "duplicate_rate": 0.0,
        "reorder_rate": 0.0,
        "gossip_period_ms": 50,
        "observable_attack": True,
        "conflict_detected": True,
        "evidence_generated": True,
        "evidence_count": 2,
        "detection_e2e_ms": 150,
        "detection_e2e_simulated_ms": 150,
        "detection_logic_ms": 1.25,
        "detection_logic_wall_ms": 1.25,
        "attack_to_evidence_wall_ms": 20.0,
        "total_wall_ms": 80.0,
        "signer_setup_ms": 10.0,
        "background_load": {},
        "gossip_events": {},
    }
    row = flatten_result(result)
    summary = summarize([row])[0]

    assert row["detection_e2e_simulated_ms"] == 150
    assert row["detection_logic_wall_ms"] == 1.25
    assert summary["mean_detection_e2e_simulated_ms"] == 150
    assert summary["mean_detection_logic_wall_ms"] == 1.25
    assert summary["mean_attack_to_evidence_wall_ms"] == 20.0
