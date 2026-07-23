from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from .commitment import CommitmentFactory
from .crypto import MockHMACSigner
from .models import ResultCode, TrajectoryEnvelope
from .witness import WitnessNode


SUBJECT_KEY = b"vehicle-A-test-key"
WITNESS_KEY = b"witness-1-test-key"
NOW = 1_000_000


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
    return [
        envelope(i, lane_id, behavior_code, base_pos + i * 2_500)
        for i in range(4)
    ]


def build_fixture() -> tuple[CommitmentFactory, WitnessNode]:
    signer = MockHMACSigner()
    factory = CommitmentFactory(signer)
    witness = WitnessNode(
        witness_id="RSU-1",
        subject_signer=signer,
        witness_signer=signer,
        subject_public_keys={"Vehicle-A": SUBJECT_KEY},
        witness_private_key=WITNESS_KEY,
        now_ms=lambda: NOW,
    )
    return factory, witness


def print_result(name: str, result) -> None:
    print(f"{name:<36} -> {result.code.value:<18} {result.reason}")


def main() -> None:
    factory, witness = build_fixture()

    c0 = factory.create(
        subject_id="Vehicle-A",
        session_id="MERGE-001",
        epoch=1,
        sequence=0,
        valid_from_ms=NOW - 100,
        valid_until_ms=NOW + 10_000,
        envelopes=plan("1", "LANE_KEEP", 100_000),
        private_key=SUBJECT_KEY,
    )
    r1 = witness.process(c0)
    print_result("1. initial commitment", r1)

    r2 = witness.process(c0)
    print_result("2. duplicate commitment", r2)

    c1a = factory.create(
        subject_id="Vehicle-A",
        session_id="MERGE-001",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=plan("2", "LANE_CHANGE_LEFT", 110_000),
        parent_root=c0.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=SUBJECT_KEY,
    )
    r3 = witness.process(c1a)
    print_result("3. valid re-commitment", r3)

    c1b = factory.create(
        subject_id="Vehicle-A",
        session_id="MERGE-001",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=plan("3", "LANE_CHANGE_RIGHT", 110_000),
        parent_root=c0.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=SUBJECT_KEY,
    )
    r4 = witness.process(c1b)
    print_result("4. same-sequence different root", r4)

    c2_bad_parent = factory.create(
        subject_id="Vehicle-A",
        session_id="MERGE-001",
        epoch=1,
        sequence=2,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=plan("2", "LANE_KEEP", 120_000),
        parent_root="00" * 32,
        update_reason="SIGNAL_CHANGE",
        private_key=SUBJECT_KEY,
    )
    r5 = witness.process(c2_bad_parent)
    print_result("5. invalid parent root", r5)

    c3_skip = factory.create(
        subject_id="Vehicle-A",
        session_id="MERGE-001",
        epoch=1,
        sequence=3,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=plan("2", "LANE_KEEP", 130_000),
        parent_root=c1a.merkle_root,
        update_reason="SIGNAL_CHANGE",
        private_key=SUBJECT_KEY,
    )
    r6 = witness.process(c3_skip)
    print_result("6. skipped sequence", r6)

    tampered = replace(c1a, merkle_root="ff" * 32)
    r7 = witness.process(tampered)
    print_result("7. tampered after signing", r7)

    expired = factory.create(
        subject_id="Vehicle-A",
        session_id="EXPIRED-001",
        epoch=1,
        sequence=0,
        valid_from_ms=NOW - 2_000,
        valid_until_ms=NOW - 1,
        envelopes=plan("1", "LANE_KEEP", 100_000),
        private_key=SUBJECT_KEY,
    )
    r8 = witness.process(expired)
    print_result("8. expired commitment", r8)

    assert r1.code is ResultCode.ACCEPT
    assert r2.code is ResultCode.DUPLICATE
    assert r3.code is ResultCode.VALID_UPDATE
    assert r4.code is ResultCode.CONFLICT
    assert r5.code is ResultCode.INVALID_UPDATE
    assert r6.code is ResultCode.INVALID_UPDATE
    assert r7.code is ResultCode.INVALID_SIGNATURE
    assert r8.code is ResultCode.STALE

    if r4.evidence is not None:
        output_dir = Path("artifacts")
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / "evidence_bundle.json"
        output_path.write_text(
            json.dumps(r4.evidence.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nEvidence written to: {output_path.resolve()}")

    print("\nALL SCENARIOS PASSED")


if __name__ == "__main__":
    main()
