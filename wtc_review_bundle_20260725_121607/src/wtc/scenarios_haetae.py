from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from .commitment import CommitmentFactory
from .crypto import Base64SignerAdapter
from .crypto_kpqc import HAETAESigner
from .models import ResultCode
from .scenarios import NOW, plan, print_result
from .witness import WitnessNode


def default_dll_path() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "native" / "haetae" / "libhaetae-mode2.dll"


def build_fixture(
    dll_path: str | Path | None = None,
) -> tuple[CommitmentFactory, WitnessNode, bytes]:
    path = Path(dll_path) if dll_path is not None else default_dll_path()
    raw_signer = HAETAESigner(str(path))
    signer = Base64SignerAdapter(raw_signer)

    subject_public_key, subject_private_key = signer.keygen()
    witness_public_key, witness_private_key = signer.keygen()

    factory = CommitmentFactory(signer)
    witness = WitnessNode(
        witness_id="RSU-1",
        subject_signer=signer,
        witness_signer=signer,
        subject_public_keys={"Vehicle-A": subject_public_key},
        witness_public_keys={"RSU-1": witness_public_key},
        witness_private_key=witness_private_key,
        now_ms=lambda: NOW,
    )
    return factory, witness, subject_private_key


def main() -> None:
    factory, witness, subject_private_key = build_fixture()

    c0 = factory.create(
        subject_id="Vehicle-A",
        session_id="HAETAE-MERGE-001",
        epoch=1,
        sequence=0,
        valid_from_ms=NOW - 100,
        valid_until_ms=NOW + 10_000,
        envelopes=plan("1", "LANE_KEEP", 100_000),
        private_key=subject_private_key,
    )
    r1 = witness.process(c0)
    print_result("1. HAETAE initial commitment", r1)

    c1a = factory.create(
        subject_id="Vehicle-A",
        session_id="HAETAE-MERGE-001",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=plan("2", "LANE_CHANGE_LEFT", 110_000),
        parent_root=c0.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=subject_private_key,
    )
    r2 = witness.process(c1a)
    print_result("2. HAETAE valid re-commitment", r2)

    c1b = factory.create(
        subject_id="Vehicle-A",
        session_id="HAETAE-MERGE-001",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=plan("3", "LANE_CHANGE_RIGHT", 110_000),
        parent_root=c0.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=subject_private_key,
    )
    r3 = witness.process(c1b)
    print_result("3. HAETAE equivocation", r3)

    tampered = replace(c1a, merkle_root="ff" * 32)
    r4 = witness.process(tampered)
    print_result("4. HAETAE tampered commitment", r4)

    assert r1.code is ResultCode.ACCEPT
    assert r2.code is ResultCode.VALID_UPDATE
    assert r3.code is ResultCode.CONFLICT
    assert r4.code is ResultCode.INVALID_SIGNATURE
    assert isinstance(c0.signature, str)
    assert r3.evidence is not None

    output_dir = Path("artifacts")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "evidence_bundle_haetae.json"
    output_path.write_text(
        json.dumps(r3.evidence.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nEvidence written to: {output_path.resolve()}")
    print("HAETAE WTC END-TO-END: PASS")


if __name__ == "__main__":
    main()
