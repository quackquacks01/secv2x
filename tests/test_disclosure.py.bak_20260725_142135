from __future__ import annotations

from dataclasses import replace

from src.wtc.commitment import CommitmentFactory
from src.wtc.crypto import MockHMACSigner
from src.wtc.disclosure import create_disclosure, verify_disclosure
from src.wtc.models import TrajectoryEnvelope


KEY = b"test-key"


def envelopes(count: int = 5) -> list[TrajectoryEnvelope]:
    return [
        TrajectoryEnvelope(
            segment_index=index,
            t_start_ms=1_000 + index * 200,
            t_end_ms=1_000 + (index + 1) * 200,
            road_id="E0",
            lane_id="E0_0",
            pos_min_mm=100_000 + index * 1_000,
            pos_max_mm=101_000 + index * 1_000,
            v_min_mmps=10_000,
            v_max_mmps=15_000,
            a_min_mmps2=-1_000,
            a_max_mmps2=1_000,
            behavior_code="LANE_KEEP",
        )
        for index in range(count)
    ]


def make_commitment(items: list[TrajectoryEnvelope]):
    return CommitmentFactory(MockHMACSigner()).create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=0,
        valid_from_ms=1_000,
        valid_until_ms=10_000,
        envelopes=items,
        private_key=KEY,
    )


def test_disclosure_verifies_against_signed_root():
    items = envelopes()
    commitment = make_commitment(items)

    disclosure = create_disclosure(
        commitment,
        items,
        slot_index=3,
        disclosed_at_ms=items[3].t_start_ms,
    )

    assert verify_disclosure(
        commitment,
        disclosure,
        enforce_slot_time=True,
    )


def test_tampered_disclosure_is_rejected():
    items = envelopes()
    commitment = make_commitment(items)
    disclosure = create_disclosure(
        commitment,
        items,
        slot_index=1,
        disclosed_at_ms=items[1].t_start_ms,
    )
    tampered = replace(
        disclosure,
        envelope=replace(
            disclosure.envelope,
            pos_max_mm=disclosure.envelope.pos_max_mm + 1,
        ),
    )

    assert not verify_disclosure(
        commitment,
        tampered,
        enforce_slot_time=True,
    )


def test_disclosure_rejects_wrong_time_when_enforced():
    items = envelopes()
    commitment = make_commitment(items)
    disclosure = create_disclosure(
        commitment,
        items,
        slot_index=0,
        disclosed_at_ms=items[0].t_end_ms,
    )

    assert not verify_disclosure(
        commitment,
        disclosure,
        enforce_slot_time=True,
    )
