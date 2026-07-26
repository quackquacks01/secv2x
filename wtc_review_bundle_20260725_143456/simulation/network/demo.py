from __future__ import annotations

import asyncio
import json
from pathlib import Path

from simulation.network.emulator import GossipNetworkEmulator
from src.wtc.commitment import CommitmentFactory
from src.wtc.crypto import MockHMACSigner
from src.wtc.models import Commitment, ResultCode, TrajectoryEnvelope, WitnessReceipt
from src.wtc.witness import WitnessNode


SUBJECT_KEY = b"vehicle-subject-key"
WITNESS_KEY_1 = b"witness-1-key"
WITNESS_KEY_2 = b"witness-2-key"


def _envelope(
    *,
    behavior_code: str,
    pos_start_mm: int,
    lane_id: str = "1",
) -> TrajectoryEnvelope:
    return TrajectoryEnvelope(
        segment_index=0,
        t_start_ms=0,
        t_end_ms=200,
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


def _create_witness_pair(now_ms: int = 1_000) -> tuple[WitnessNode, WitnessNode, CommitmentFactory]:
    signer = MockHMACSigner()
    factory = CommitmentFactory(signer)

    witness_1 = WitnessNode(
        witness_id="RSU-1",
        subject_signer=signer,
        witness_signer=signer,
        subject_public_keys={"Vehicle-A": SUBJECT_KEY},
        witness_private_key=WITNESS_KEY_1,
        witness_public_keys={"RSU-2": WITNESS_KEY_2},
        now_ms=lambda: now_ms,
    )
    witness_2 = WitnessNode(
        witness_id="RSU-2",
        subject_signer=signer,
        witness_signer=signer,
        subject_public_keys={"Vehicle-A": SUBJECT_KEY},
        witness_private_key=WITNESS_KEY_2,
        witness_public_keys={"RSU-1": WITNESS_KEY_1},
        now_ms=lambda: now_ms,
    )
    return witness_1, witness_2, factory


def _initial_commitment(factory: CommitmentFactory) -> Commitment:
    return factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=0,
        valid_from_ms=0,
        valid_until_ms=10_000,
        envelopes=[_envelope(behavior_code="KEEP", pos_start_mm=100_000)],
        private_key=SUBJECT_KEY,
    )


async def _delay_demo() -> None:
    witness_1, _, factory = _create_witness_pair()
    commitment = _initial_commitment(factory)
    receipt = witness_1._make_receipt(commitment, 0, decision="ACCEPTED")

    emulator = GossipNetworkEmulator(base_delay_ms=100, jitter_ms=0, seed=1)
    received_at: list[int] = []

    async def handler(_: Commitment, __: WitnessReceipt) -> ResultCode:
        received_at.append(emulator.current_time_ms)
        return ResultCode.ACCEPT

    emulator.register_handler("RSU-2", handler)
    emulator.send_gossip("RSU-1", "RSU-2", commitment, receipt)
    await emulator.run_until_empty()

    if received_at != [100]:
        raise AssertionError(f"delay demo failed: received_at={received_at}")
    print("DELAY TEST       : PASS (100 ms)")


async def _loss_demo() -> None:
    witness_1, _, factory = _create_witness_pair()
    commitment = _initial_commitment(factory)
    receipt = witness_1._make_receipt(commitment, 0, decision="ACCEPTED")

    emulator = GossipNetworkEmulator(loss_rate=1.0, seed=2)
    delivered: list[Commitment] = []

    async def handler(commitment_in: Commitment, _: WitnessReceipt) -> ResultCode:
        delivered.append(commitment_in)
        return ResultCode.ACCEPT

    emulator.register_handler("RSU-2", handler)
    emulator.send_gossip("RSU-1", "RSU-2", commitment, receipt)
    await emulator.run_until_empty()

    if delivered:
        raise AssertionError("loss demo failed: a dropped packet was delivered")
    print("LOSS TEST        : PASS (100% loss -> no delivery)")


async def _duplicate_demo() -> None:
    witness_1, _, factory = _create_witness_pair()
    commitment = _initial_commitment(factory)
    receipt = witness_1._make_receipt(commitment, 0, decision="ACCEPTED")

    emulator = GossipNetworkEmulator(duplicate_rate=1.0, seed=3)
    delivered_count = 0

    async def handler(_: Commitment, __: WitnessReceipt) -> ResultCode:
        nonlocal delivered_count
        delivered_count += 1
        return ResultCode.ACCEPT

    emulator.register_handler("RSU-2", handler)
    emulator.send_gossip("RSU-1", "RSU-2", commitment, receipt)
    await emulator.run_until_empty()

    if delivered_count != 2:
        raise AssertionError(f"duplicate demo failed: delivered_count={delivered_count}")
    print("DUPLICATE TEST   : PASS (1 original + 1 duplicate)")


async def _reorder_demo() -> None:
    witness_1, _, factory = _create_witness_pair()
    commitment_a = _initial_commitment(factory)
    commitment_b = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=1,
        valid_from_ms=0,
        valid_until_ms=10_000,
        envelopes=[_envelope(behavior_code="CHANGE", pos_start_mm=102_000)],
        parent_root=commitment_a.merkle_root,
        update_reason="UPDATE",
        private_key=SUBJECT_KEY,
    )
    receipt_a = witness_1._make_receipt(commitment_a, 0, decision="ACCEPTED")
    receipt_b = witness_1._make_receipt(commitment_b, 0, decision="ACCEPTED")

    class FixedRandom:
        def __init__(self) -> None:
            self.uniform_call_index = 0

        def random(self) -> float:
            return 0.0

        def uniform(self, _a: float, _b: float) -> float:
            self.uniform_call_index += 1
            return 40.0 if self.uniform_call_index == 1 else 10.0

    emulator = GossipNetworkEmulator(base_delay_ms=100, reorder_rate=1.0)
    emulator.random = FixedRandom()  # type: ignore[assignment]
    order: list[str] = []

    async def handler(commitment_in: Commitment, _: WitnessReceipt) -> ResultCode:
        order.append(commitment_in.merkle_root)
        return ResultCode.ACCEPT

    emulator.register_handler("RSU-2", handler)
    emulator.send_gossip("RSU-1", "RSU-2", commitment_a, receipt_a)
    emulator.send_gossip("RSU-1", "RSU-2", commitment_b, receipt_b)
    await emulator.run_until_empty()

    expected = [commitment_b.merkle_root, commitment_a.merkle_root]
    if order != expected:
        raise AssertionError(f"reorder demo failed: order={order}, expected={expected}")
    print("REORDER TEST     : PASS (second message arrived first)")


async def _gossip_conflict_demo() -> Path:
    witness_1, witness_2, factory = _create_witness_pair(now_ms=1_000)

    initial = _initial_commitment(factory)
    if witness_1.process(initial).code is not ResultCode.ACCEPT:
        raise AssertionError("RSU-1 failed to accept initial commitment")
    if witness_2.process(initial).code is not ResultCode.ACCEPT:
        raise AssertionError("RSU-2 failed to accept initial commitment")

    update_a = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=1,
        valid_from_ms=0,
        valid_until_ms=10_000,
        envelopes=[_envelope(behavior_code="LEFT", pos_start_mm=105_000)],
        parent_root=initial.merkle_root,
        update_reason="LEFT_PLAN",
        private_key=SUBJECT_KEY,
    )
    update_b = factory.create(
        subject_id="Vehicle-A",
        session_id="SESSION-1",
        epoch=1,
        sequence=1,
        valid_from_ms=0,
        valid_until_ms=10_000,
        envelopes=[_envelope(behavior_code="RIGHT", pos_start_mm=108_000)],
        parent_root=initial.merkle_root,
        update_reason="RIGHT_PLAN",
        private_key=SUBJECT_KEY,
    )

    result_a = witness_1.process(update_a)
    result_b = witness_2.process(update_b)
    if result_a.code is not ResultCode.VALID_UPDATE or result_a.receipt is None:
        raise AssertionError(f"RSU-1 update result is {result_a.code}")
    if result_b.code is not ResultCode.VALID_UPDATE or result_b.receipt is None:
        raise AssertionError(f"RSU-2 update result is {result_b.code}")

    received_codes: list[ResultCode] = []
    evidence_objects = []

    async def rsu_1_handler(commitment_in: Commitment, receipt_in: WitnessReceipt) -> ResultCode:
        result = witness_1.process_gossip(commitment_in, receipt_in, None)
        received_codes.append(result.code)
        if result.evidence is not None:
            evidence_objects.append(result.evidence)
        return result.code

    emulator = GossipNetworkEmulator(base_delay_ms=50, seed=4)
    emulator.register_handler("RSU-1", rsu_1_handler)
    emulator.send_gossip("RSU-2", "RSU-1", update_b, result_b.receipt)
    await emulator.run_until_empty()

    if received_codes != [ResultCode.CONFLICT]:
        raise AssertionError(f"gossip conflict demo failed: result={received_codes}")
    if not evidence_objects:
        raise AssertionError("gossip conflict demo failed: Evidence Bundle was not created")

    evidence = evidence_objects[0]
    output_path = Path("artifacts") / "evidence_bundle_network_demo.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(evidence.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"GOSSIP CONFLICT  : PASS ({update_a.merkle_root[:12]}... != {update_b.merkle_root[:12]}...)")
    print(f"EVIDENCE BUNDLE  : PASS ({output_path})")
    return output_path


async def main() -> None:
    print("=== KpqC WTC ASYNC NETWORK EMULATOR DEMO ===")
    await _delay_demo()
    await _loss_demo()
    await _duplicate_demo()
    await _reorder_demo()
    await _gossip_conflict_demo()
    print("NETWORK EMULATOR : PASS")


if __name__ == "__main__":
    asyncio.run(main())
