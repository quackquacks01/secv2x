from __future__ import annotations

from src.wtc.commitment import CommitmentFactory
from src.wtc.crypto import MockHMACSigner
from src.wtc.models import ResultCode, TrajectoryEnvelope
from src.wtc.witness import WitnessNode


KEY = b"subject"
WITNESS_KEY = b"witness"


def test_initial_commitment_receipt_is_accepted():
    signer = MockHMACSigner()
    envelope = TrajectoryEnvelope(
        segment_index=0,
        t_start_ms=1_000,
        t_end_ms=1_200,
        road_id="E0",
        lane_id="E0_0",
        pos_min_mm=0,
        pos_max_mm=1_000,
        v_min_mmps=0,
        v_max_mmps=1_000,
        a_min_mmps2=-100,
        a_max_mmps2=100,
        behavior_code="LANE_KEEP",
    )
    commitment = CommitmentFactory(signer).create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=0,
        valid_from_ms=1_000,
        valid_until_ms=2_000,
        envelopes=[envelope],
        private_key=KEY,
    )
    witness = WitnessNode(
        witness_id="Witness-W1",
        subject_signer=signer,
        witness_signer=signer,
        subject_public_keys={"Vehicle-A": KEY},
        witness_private_key=WITNESS_KEY,
        witness_public_keys={},
        now_ms=lambda: 1_000,
    )

    result = witness.process(commitment)

    assert result.code is ResultCode.ACCEPT
    assert result.receipt is not None
    assert result.receipt.decision == "ACCEPTED"
