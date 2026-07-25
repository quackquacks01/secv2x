from __future__ import annotations

from simulation.sumo.controllers.run_wtc_sumo import (
    VehicleState,
    create_attack_plans,
    state_to_envelopes,
)
from src.wtc.commitment import CommitmentFactory
from src.wtc.crypto import MockHMACSigner


def sample_state() -> VehicleState:
    return VehicleState(
        vehicle_id="Vehicle-A",
        simulation_time_ms=1_000,
        x_m=10.0,
        y_m=1.6,
        lane_position_m=10.0,
        speed_mps=10.0,
        acceleration_mps2=1.0,
        lane_id="E0_0",
        road_id="E0",
    )


def test_state_is_converted_to_integer_envelopes():
    envelopes = state_to_envelopes(
        sample_state(),
        slot_count=3,
        slot_ms=200,
    )

    assert len(envelopes) == 3
    assert envelopes[0].segment_index == 0
    assert envelopes[0].t_start_ms == 1_000
    assert envelopes[0].t_end_ms == 1_200
    assert envelopes[0].road_id == "E0"
    assert envelopes[0].lane_id == "E0_0"
    assert isinstance(envelopes[0].pos_min_mm, int)
    assert isinstance(envelopes[0].v_max_mmps, int)


def test_future_slots_move_forward_for_positive_speed():
    envelopes = state_to_envelopes(
        sample_state(),
        slot_count=3,
        slot_ms=200,
    )

    assert envelopes[1].pos_min_mm > envelopes[0].pos_min_mm
    assert envelopes[2].pos_min_mm > envelopes[1].pos_min_mm


def test_attack_plans_generate_different_merkle_roots():
    left, right = create_attack_plans(
        sample_state(),
        slot_count=5,
        slot_ms=200,
    )
    signer = MockHMACSigner()
    factory = CommitmentFactory(signer)

    initial = factory.create(
        subject_id="Vehicle-A",
        session_id="TEST",
        epoch=1,
        sequence=0,
        valid_from_ms=1_000,
        valid_until_ms=10_000,
        envelopes=state_to_envelopes(
            sample_state(),
            slot_count=5,
            slot_ms=200,
        ),
        private_key=b"key",
    )
    commitment_left = factory.create(
        subject_id="Vehicle-A",
        session_id="TEST",
        epoch=1,
        sequence=1,
        valid_from_ms=1_000,
        valid_until_ms=10_000,
        envelopes=left,
        parent_root=initial.merkle_root,
        update_reason="LEFT",
        private_key=b"key",
    )
    commitment_right = factory.create(
        subject_id="Vehicle-A",
        session_id="TEST",
        epoch=1,
        sequence=1,
        valid_from_ms=1_000,
        valid_until_ms=10_000,
        envelopes=right,
        parent_root=initial.merkle_root,
        update_reason="RIGHT",
        private_key=b"key",
    )

    assert commitment_left.consistency_key == commitment_right.consistency_key
    assert commitment_left.merkle_root != commitment_right.merkle_root
