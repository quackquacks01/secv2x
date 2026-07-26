from __future__ import annotations

from dataclasses import dataclass

from simulation.sumo.controllers.run_wtc_reveal import (
    unpack_subject_state_result,
)


@dataclass
class DummyState:
    vehicle_id: str = "Vehicle-A"
    lane_id: str = "E0_0"


def test_unpacks_current_collect_subject_state_tuple():
    state = DummyState()

    unpacked, observed = unpack_subject_state_result(
        (state, ["Vehicle-A", "Witness-W1"])
    )

    assert unpacked is state
    assert unpacked.lane_id == "E0_0"
    assert observed == ["Vehicle-A", "Witness-W1"]


def test_accepts_legacy_state_only_return():
    state = DummyState()

    unpacked, observed = unpack_subject_state_result(state)

    assert unpacked is state
    assert observed == ["Vehicle-A"]
