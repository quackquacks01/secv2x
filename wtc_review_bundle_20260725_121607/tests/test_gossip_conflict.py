from __future__ import annotations

from src.wtc.commitment import CommitmentFactory
from src.wtc.crypto import MockHMACSigner
from src.wtc.models import ResultCode, TrajectoryEnvelope
from src.wtc.witness import WitnessNode


SUBJECT_KEY = b"vehicle-subject-key"
WITNESS_KEY_1 = b"witness-1-key"
WITNESS_KEY_2 = b"witness-2-key"


def test_gossip_conflict_creates_evidence_bundle():
    signer = MockHMACSigner()
    factory = CommitmentFactory(signer)

    witness_1 = WitnessNode(
        witness_id="RSU-1",
        subject_signer=signer,
        witness_signer=signer,
        subject_public_keys={"Vehicle-A": SUBJECT_KEY},
        witness_private_key=WITNESS_KEY_1,
        witness_public_keys={"RSU-2": WITNESS_KEY_2},
        now_ms=lambda: 1_000,
    )
    witness_2 = WitnessNode(
        witness_id="RSU-2",
        subject_signer=signer,
        witness_signer=signer,
        subject_public_keys={"Vehicle-A": SUBJECT_KEY},
        witness_private_key=WITNESS_KEY_2,
        witness_public_keys={"RSU-1": WITNESS_KEY_1},
        now_ms=lambda: 1_000,
    )

    initial = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=0,
        valid_from_ms=0,
        valid_until_ms=10_000,
        envelopes=[
            TrajectoryEnvelope(
                segment_index=0,
                t_start_ms=0,
                t_end_ms=200,
                road_id="R12",
                lane_id="1",
                pos_min_mm=100_000,
                pos_max_mm=102_000,
                v_min_mmps=12_000,
                v_max_mmps=15_000,
                a_min_mmps2=-3_000,
                a_max_mmps2=2_000,
                behavior_code="KEEP",
            )
        ],
        private_key=SUBJECT_KEY,
    )
    witness_1.process(initial)
    witness_2.process(initial)

    update_a = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=1,
        valid_from_ms=0,
        valid_until_ms=10_000,
        envelopes=[
            TrajectoryEnvelope(
                segment_index=0,
                t_start_ms=0,
                t_end_ms=200,
                road_id="R12",
                lane_id="1",
                pos_min_mm=105_000,
                pos_max_mm=107_000,
                v_min_mmps=12_000,
                v_max_mmps=15_000,
                a_min_mmps2=-3_000,
                a_max_mmps2=2_000,
                behavior_code="A",
            )
        ],
        parent_root=initial.merkle_root,
        update_reason="A",
        private_key=SUBJECT_KEY,
    )
    update_b = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=1,
        valid_from_ms=0,
        valid_until_ms=10_000,
        envelopes=[
            TrajectoryEnvelope(
                segment_index=0,
                t_start_ms=0,
                t_end_ms=200,
                road_id="R12",
                lane_id="1",
                pos_min_mm=108_000,
                pos_max_mm=110_000,
                v_min_mmps=12_000,
                v_max_mmps=15_000,
                a_min_mmps2=-3_000,
                a_max_mmps2=2_000,
                behavior_code="B",
            )
        ],
        parent_root=initial.merkle_root,
        update_reason="B",
        private_key=SUBJECT_KEY,
    )

    assert witness_1.process(update_a).code is ResultCode.VALID_UPDATE
    assert witness_2.process(update_b).code is ResultCode.VALID_UPDATE

    receipt_b = witness_2._make_receipt(update_b, 1_000, decision="ACCEPTED")
    result = witness_1.process_gossip(update_b, receipt_b, None)

    assert result.code is ResultCode.CONFLICT
    assert result.evidence is not None
    assert result.evidence.commitment_a.merkle_root == update_a.merkle_root
    assert result.evidence.commitment_b.merkle_root == update_b.merkle_root
    assert result.evidence.receipt_a is not None
    assert result.evidence.receipt_b is not None
    assert witness_1.active_head_cache[update_a.session_key].merkle_root == update_a.merkle_root
