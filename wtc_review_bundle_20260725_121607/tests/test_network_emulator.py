from __future__ import annotations

import asyncio

from src.wtc.commitment import CommitmentFactory
from src.wtc.crypto import MockHMACSigner
from src.wtc.models import ResultCode, TrajectoryEnvelope
from src.wtc.witness import WitnessNode
from simulation.network.emulator import GossipNetworkEmulator


SUBJECT_KEY = b"vehicle-subject-key"
WITNESS_KEY_1 = b"witness-1-key"
WITNESS_KEY_2 = b"witness-2-key"


def envelope(
    segment_index: int,
    lane_id: str,
    behavior_code: str,
    pos_start_mm: int,
) -> TrajectoryEnvelope:
    return TrajectoryEnvelope(
        segment_index=segment_index,
        t_start_ms=segment_index * 200,
        t_end_ms=(segment_index + 1) * 200,
        road_id="R12",
        lane_id=lane_id,
        pos_min_mm=pos_start_mm,
        pos_max_mm=pos_start_mm + 2_000,
        v_min_mmps=12_000,
        v_max_mmps=15_000,
        a_min_mmps2=-3_000,
        a_max_mmps2=2_000,
        behavior_code=behavior_code,
    )


def plan(lane_id: str, behavior_code: str, base_pos: int) -> list[TrajectoryEnvelope]:
    return [envelope(0, lane_id, behavior_code, base_pos)]


def create_witness_pair() -> tuple[WitnessNode, WitnessNode, CommitmentFactory]:
    signer = MockHMACSigner()
    factory = CommitmentFactory(signer)
    witness_1 = WitnessNode(
        witness_id="RSU-1",
        subject_signer=signer,
        witness_signer=signer,
        subject_public_keys={"Vehicle-A": SUBJECT_KEY},
        witness_private_key=WITNESS_KEY_1,
        witness_public_keys={"RSU-2": WITNESS_KEY_2},
        now_ms=lambda: 0,
    )
    witness_2 = WitnessNode(
        witness_id="RSU-2",
        subject_signer=signer,
        witness_signer=signer,
        subject_public_keys={"Vehicle-A": SUBJECT_KEY},
        witness_private_key=WITNESS_KEY_2,
        witness_public_keys={"RSU-1": WITNESS_KEY_1},
        now_ms=lambda: 0,
    )
    return witness_1, witness_2, factory


def test_delay_is_applied_to_delivery():
    witness_1, witness_2, factory = create_witness_pair()
    commitment = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=0,
        valid_from_ms=0,
        valid_until_ms=10_000,
        envelopes=plan("1", "KEEP", 100_000),
        private_key=SUBJECT_KEY,
    )
    receipt = witness_1._make_receipt(commitment, 0, decision="ACCEPTED")
    emulator = GossipNetworkEmulator(base_delay_ms=100, jitter_ms=0, seed=1)
    received: list[int] = []

    async def handler(commitment_in, receipt_in):
        received.append(emulator.current_time_ms)
        return ResultCode.ACCEPT

    emulator.register_handler("RSU-2", handler)
    emulator.send_gossip("RSU-1", "RSU-2", commitment, receipt)
    asyncio.run(emulator.run_until_empty())

    assert received == [100]
    assert any(event.event_type == "sent" for event in emulator.events)
    assert any(event.event_type == "delivered" for event in emulator.events)


def test_packet_loss_prevents_delivery():
    witness_1, witness_2, factory = create_witness_pair()
    commitment = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=0,
        valid_from_ms=0,
        valid_until_ms=10_000,
        envelopes=plan("1", "KEEP", 100_000),
        private_key=SUBJECT_KEY,
    )
    receipt = witness_1._make_receipt(commitment, 0, decision="ACCEPTED")
    emulator = GossipNetworkEmulator(loss_rate=1.0, seed=2)
    delivered: list[tuple] = []

    async def handler(commitment_in, receipt_in):
        delivered.append((commitment_in, receipt_in))
        return ResultCode.ACCEPT

    emulator.register_handler("RSU-2", handler)
    emulator.send_gossip("RSU-1", "RSU-2", commitment, receipt)
    asyncio.run(emulator.run_until_empty())

    assert not delivered
    assert any(event.event_type == "dropped" for event in emulator.events)


def test_duplicate_messages_can_be_delivered_multiple_times():
    witness_1, witness_2, factory = create_witness_pair()
    commitment = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=0,
        valid_from_ms=0,
        valid_until_ms=10_000,
        envelopes=plan("1", "KEEP", 100_000),
        private_key=SUBJECT_KEY,
    )
    receipt = witness_1._make_receipt(commitment, 0, decision="ACCEPTED")
    emulator = GossipNetworkEmulator(base_delay_ms=0, jitter_ms=0, duplicate_rate=1.0, seed=3)
    delivered: list[tuple] = []

    async def handler(commitment_in, receipt_in):
        delivered.append((commitment_in, receipt_in))
        return ResultCode.ACCEPT

    emulator.register_handler("RSU-2", handler)
    emulator.send_gossip("RSU-1", "RSU-2", commitment, receipt)
    asyncio.run(emulator.run_until_empty())

    assert len(delivered) == 2
    assert sum(1 for event in emulator.events if event.event_type == "duplicated") == 1


def test_message_order_can_change_when_reordered():
    witness_1, witness_2, factory = create_witness_pair()
    commitment_a = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=0,
        valid_from_ms=0,
        valid_until_ms=10_000,
        envelopes=plan("1", "KEEP", 100_000),
        private_key=SUBJECT_KEY,
    )
    commitment_b = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=1,
        valid_from_ms=0,
        valid_until_ms=10_000,
        envelopes=plan("1", "CHANGE", 102_000),
        parent_root=commitment_a.merkle_root,
        update_reason="UPDATE",
        private_key=SUBJECT_KEY,
    )
    receipt_a = witness_1._make_receipt(commitment_a, 0, decision="ACCEPTED")
    receipt_b = witness_1._make_receipt(commitment_b, 0, decision="ACCEPTED")

    class FixedRandom:
        """첫 메시지는 40 ms, 두 번째 메시지는 10 ms 뒤에 전달한다.

        random() 호출 횟수와 uniform() 호출 횟수를 분리해야
        loss/reorder/duplicate 판정용 random() 호출이 지연값 순서를 흔들지 않는다.
        """

        def __init__(self) -> None:
            self.uniform_call_index = 0

        def random(self) -> float:
            # loss_rate=0, duplicate_rate=0에서는 0.0 < 0.0이 False이고,
            # reorder_rate=1에서는 0.0 < 1.0이 True가 된다.
            return 0.0

        def uniform(self, a: float, b: float) -> float:
            self.uniform_call_index += 1
            return 40.0 if self.uniform_call_index == 1 else 10.0

    emulator = GossipNetworkEmulator(base_delay_ms=100, jitter_ms=0, reorder_rate=1.0)
    emulator.random = FixedRandom()
    order: list[str] = []

    async def handler(commitment_in, receipt_in):
        order.append(commitment_in.merkle_root)
        return ResultCode.ACCEPT

    emulator.register_handler("RSU-2", handler)
    emulator.send_gossip("RSU-1", "RSU-2", commitment_a, receipt_a)
    emulator.send_gossip("RSU-1", "RSU-2", commitment_b, receipt_b)
    asyncio.run(emulator.run_until_empty())

    assert order == [commitment_b.merkle_root, commitment_a.merkle_root]


def test_gossip_is_delivered_to_a_remote_witness():
    witness_1, witness_2, factory = create_witness_pair()
    commitment = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=0,
        valid_from_ms=0,
        valid_until_ms=10_000,
        envelopes=plan("1", "KEEP", 100_000),
        private_key=SUBJECT_KEY,
    )
    result = witness_1.process(commitment)
    assert result.code is ResultCode.ACCEPT
    receipt = witness_1._make_receipt(commitment, 0, decision="ACCEPTED")
    received_results: list[ResultCode] = []

    async def handler(commitment_in, receipt_in):
        remote_result = witness_2.process_gossip(commitment_in, receipt_in, None)
        received_results.append(remote_result.code)
        return remote_result.code

    emulator = GossipNetworkEmulator(base_delay_ms=10, jitter_ms=0, seed=5)
    emulator.register_handler("RSU-2", handler)
    emulator.send_gossip("RSU-1", "RSU-2", commitment, receipt)
    asyncio.run(emulator.run_until_empty())

    assert received_results == [ResultCode.ACCEPT]
    assert witness_2.receipts_by_consistency_key[commitment.consistency_key].commitment_digest == receipt.commitment_digest
