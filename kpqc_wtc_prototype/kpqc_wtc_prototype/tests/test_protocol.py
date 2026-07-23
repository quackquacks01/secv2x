from dataclasses import replace

from wtc.commitment import CommitmentFactory
from wtc.crypto import MockHMACSigner
from wtc.models import ResultCode, TrajectoryEnvelope
from wtc.witness import WitnessNode


NOW = 1_000_000
SUBJECT_KEY = b"subject-test-key"
WITNESS_KEY = b"witness-test-key"


def make_plan(lane: str, behavior: str) -> list[TrajectoryEnvelope]:
    return [
        TrajectoryEnvelope(
            segment_index=i,
            t_start_ms=i * 200,
            t_end_ms=(i + 1) * 200,
            road_id="R12",
            lane_id=lane,
            pos_min_mm=100_000 + i * 2_000,
            pos_max_mm=101_000 + i * 2_000,
            v_min_mmps=10_000,
            v_max_mmps=15_000,
            a_min_mmps2=-3_000,
            a_max_mmps2=2_000,
            behavior_code=behavior,
        )
        for i in range(4)
    ]


def fixture():
    signer = MockHMACSigner()
    factory = CommitmentFactory(signer)
    witness = WitnessNode(
        witness_id="RSU-1",
        subject_signer=signer,
        witness_signer=signer,
        subject_public_keys={"Vehicle-A": SUBJECT_KEY},
        witness_public_keys={"RSU-1": WITNESS_KEY},
        witness_private_key=WITNESS_KEY,
        now_ms=lambda: NOW,
    )
    return factory, witness


def create_initial(factory):
    return factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=0,
        valid_from_ms=NOW - 10,
        valid_until_ms=NOW + 10_000,
        envelopes=make_plan("1", "KEEP"),
        private_key=SUBJECT_KEY,
    )


def test_accept_and_duplicate():
    factory, witness = fixture()
    c0 = create_initial(factory)

    first = witness.process(c0)
    second = witness.process(c0)

    assert first.code is ResultCode.ACCEPT
    assert second.code is ResultCode.DUPLICATE


def test_valid_update():
    factory, witness = fixture()
    c0 = create_initial(factory)
    assert witness.process(c0).code is ResultCode.ACCEPT

    c1 = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=make_plan("2", "LEFT"),
        parent_root=c0.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=SUBJECT_KEY,
    )

    assert witness.process(c1).code is ResultCode.VALID_UPDATE


def test_same_key_different_root_is_conflict_and_does_not_replace_head():
    factory, witness = fixture()
    c0 = create_initial(factory)
    witness.process(c0)

    c1a = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=make_plan("2", "LEFT"),
        parent_root=c0.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=SUBJECT_KEY,
    )
    c1b = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=make_plan("3", "RIGHT"),
        parent_root=c0.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=SUBJECT_KEY,
    )

    assert witness.process(c1a).code is ResultCode.VALID_UPDATE
    result = witness.process(c1b)

    assert result.code is ResultCode.CONFLICT
    assert result.evidence is not None
    assert witness.latest_by_session[c1a.session_key].merkle_root == c1a.merkle_root


def test_invalid_parent_root():
    factory, witness = fixture()
    c0 = create_initial(factory)
    witness.process(c0)

    c1 = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=make_plan("2", "LEFT"),
        parent_root="00" * 32,
        update_reason="OBSTACLE_AVOID",
        private_key=SUBJECT_KEY,
    )

    assert witness.process(c1).code is ResultCode.INVALID_UPDATE


def test_sequence_skip_is_invalid_update():
    factory, witness = fixture()
    c0 = create_initial(factory)
    witness.process(c0)

    c2 = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=2,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=make_plan("2", "LEFT"),
        parent_root=c0.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=SUBJECT_KEY,
    )

    assert witness.process(c2).code is ResultCode.INVALID_UPDATE


def test_out_of_order_sequence_is_pending_update():
    factory, witness = fixture()
    c0 = create_initial(factory)
    witness.process(c0)

    pending = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=2,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=make_plan("2", "LEFT"),
        parent_root="11" * 32,
        update_reason="OBSTACLE_AVOID",
        private_key=SUBJECT_KEY,
    )

    result = witness.process(pending)

    assert result.code is ResultCode.PENDING_UPDATE
    assert result.receipt is not None
    assert result.receipt.decision == "PENDING"


def test_pending_update_is_resolved_when_missing_parent_arrives():
    factory, witness = fixture()
    c0 = create_initial(factory)
    witness.process(c0)

    c1 = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=make_plan("2", "LEFT"),
        parent_root=c0.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=SUBJECT_KEY,
    )
    c2 = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=2,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=make_plan("3", "RIGHT"),
        parent_root=c1.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=SUBJECT_KEY,
    )

    assert witness.process(c2).code is ResultCode.PENDING_UPDATE
    assert len(witness.pending_update_cache[c2.consistency_key]) == 1

    result = witness.process(c1)

    assert result.code is ResultCode.VALID_UPDATE
    assert witness.latest_by_session[c1.session_key].merkle_root == c2.merkle_root
    assert c1.consistency_key not in witness.pending_update_cache


def test_observation_cache_records_multiple_roots():
    factory, witness = fixture()
    c0 = create_initial(factory)
    witness.process(c0)

    c1a = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=make_plan("2", "LEFT"),
        parent_root=c0.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=SUBJECT_KEY,
    )
    c1b = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=make_plan("3", "RIGHT"),
        parent_root=c0.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=SUBJECT_KEY,
    )

    witness.process(c1a)
    witness.process(c1b)

    root_map = witness.observation_cache[c1a.consistency_key]
    assert c1a.merkle_root in root_map
    assert c1b.merkle_root in root_map
    assert len(root_map[c1a.merkle_root]) == 1
    assert len(root_map[c1b.merkle_root]) == 1


def test_verified_gossip_is_accepted():
    factory, witness = fixture()
    c0 = create_initial(factory)
    witness.process(c0)

    receipt = witness._make_receipt(c0, NOW, decision="ACCEPTED")
    result = witness.process_gossip(c0, receipt, None)

    assert result.code is ResultCode.ACCEPT
    assert result.receipt is not None


def test_unknown_witness_key_rejects_gossip():
    factory, witness = fixture()
    c0 = create_initial(factory)
    witness.process(c0)

    receipt = witness._make_receipt(c0, NOW, decision="ACCEPTED")
    bad_witness = WitnessNode(
        witness_id="RSU-2",
        subject_signer=MockHMACSigner(),
        witness_signer=MockHMACSigner(),
        subject_public_keys={"Vehicle-A": SUBJECT_KEY},
        witness_public_keys={},
        witness_private_key=b"bad-key",
        now_ms=lambda: NOW,
    )
    result = bad_witness.process_gossip(c0, receipt, None)

    assert result.code is ResultCode.UNVERIFIED_GOSSIP


def test_unverified_gossip_is_rejected():
    factory, witness = fixture()
    c0 = create_initial(factory)
    witness.process(c0)

    result = witness.process_gossip(commitment=None, witness_receipt=None, witness_public_key=None)

    assert result.code is ResultCode.UNVERIFIED_GOSSIP


def test_signature_tampering_rejected_without_cache_update():
    factory, witness = fixture()
    c0 = create_initial(factory)
    tampered = replace(c0, merkle_root="ff" * 32)

    before = len(witness.active_head_cache)
    result = witness.process(tampered)
    after = len(witness.active_head_cache)

    assert result.code is ResultCode.INVALID_SIGNATURE
    assert before == after == 0


def test_expired_is_stale():
    factory, witness = fixture()
    expired = factory.create(
        subject_id="Vehicle-A",
        session_id="EXPIRED",
        epoch=1,
        sequence=0,
        valid_from_ms=NOW - 1000,
        valid_until_ms=NOW - 1,
        envelopes=make_plan("1", "KEEP"),
        private_key=SUBJECT_KEY,
    )
    assert witness.process(expired).code is ResultCode.STALE


def test_update_without_context_is_invalid():
    factory, witness = fixture()
    c0 = create_initial(factory)
    witness.process(c0)

    signer = MockHMACSigner()
    unsigned = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=make_plan("2", "LEFT"),
        parent_root=c0.merkle_root,
        update_reason="TEMP",
        private_key=SUBJECT_KEY,
    )
    from wtc.commitment import commitment_message
    without_context = replace(unsigned, context_digest=None, signature="")
    without_context = replace(
        without_context,
        signature=signer.sign(commitment_message(without_context), SUBJECT_KEY),
    )

    assert witness.process(without_context).code is ResultCode.INVALID_UPDATE
