from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.wtc.commitment import CommitmentFactory, commitment_message
from src.wtc.disclosure import create_disclosure, verify_disclosure
from src.wtc.encoding import canonical_json_bytes
from src.wtc.models import ResultCode
from src.wtc.witness import WitnessNode

from simulation.sumo.controllers.run_wtc_sumo import (
    ARTIFACT_ROOT,
    DEFAULT_SUMO_CONFIG,
    MutableClock,
    SUBJECT_ID,
    SESSION_ID,
    collect_subject_state,
    create_signer_bundle,
    state_to_envelopes,
)


def unpack_subject_state_result(result):
    """Normalize collect_subject_state() legacy and tuple return formats."""
    if isinstance(result, tuple):
        if len(result) != 2:
            raise ValueError(
                "Unexpected collect_subject_state tuple length: "
                f"{len(result)}"
            )
        state, observed_vehicle_ids = result
        return state, list(observed_vehicle_ids)

    return result, [getattr(result, "vehicle_id", SUBJECT_ID)]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and verify SUMO-derived WTC trajectory disclosures "
            "with Merkle proofs."
        )
    )
    parser.add_argument(
        "--algorithm",
        choices=("mock", "haetae", "aimer"),
        default="mock",
    )
    parser.add_argument("--sumo-config", type=Path, default=DEFAULT_SUMO_CONFIG)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--slots", type=int, default=5)
    parser.add_argument("--slot-ms", type=int, default=200)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument(
        "--haetae-dll",
        type=Path,
        default=Path("native/haetae/libhaetae-mode2.dll"),
    )
    parser.add_argument(
        "--aimer-dll",
        type=Path,
        default=Path("native/aimer/libaimer-128f.dll"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.steps <= 0 or args.slots <= 0 or args.slot_ms <= 0:
        raise ValueError("steps, slots and slot-ms must be positive")

    started_ns = time.perf_counter_ns()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    output_path = args.output_json or (
        ARTIFACT_ROOT
        / "reveal"
        / f"{stamp}_{args.algorithm}_slots{args.slots}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        state, observed_vehicle_ids = unpack_subject_state_result(
            collect_subject_state(
                sumo_config=args.sumo_config,
                gui=args.gui,
                steps=args.steps,
                print_state=False,
            )
        )
        envelopes = state_to_envelopes(
            state,
            slot_count=args.slots,
            slot_ms=args.slot_ms,
        )

        setup_started_ns = time.perf_counter_ns()
        signer_bundle = create_signer_bundle(
            args.algorithm,
            witness_count=1,
            haetae_dll=args.haetae_dll,
            aimer_dll=args.aimer_dll,
        )
        signer_setup_ms = (
            time.perf_counter_ns() - setup_started_ns
        ) / 1_000_000

        clock = MutableClock(state.simulation_time_ms)
        factory = CommitmentFactory(signer_bundle.signer)

        commitment_started_ns = time.perf_counter_ns()
        commitment = factory.create(
            subject_id=SUBJECT_ID,
            session_id=SESSION_ID,
            epoch=1,
            sequence=0,
            valid_from_ms=state.simulation_time_ms,
            valid_until_ms=(
                state.simulation_time_ms
                + args.slots * args.slot_ms
                + 5_000
            ),
            envelopes=envelopes,
            private_key=signer_bundle.subject_private_key,
        )
        commitment_create_wall_ms = (
            time.perf_counter_ns() - commitment_started_ns
        ) / 1_000_000

        signature_verify_started_ns = time.perf_counter_ns()
        commitment_signature_valid = signer_bundle.signer.verify(
            commitment_message(commitment),
            commitment.signature,
            signer_bundle.subject_public_key,
        )
        commitment_verify_wall_ms = (
            time.perf_counter_ns() - signature_verify_started_ns
        ) / 1_000_000

        witness_public, witness_private = signer_bundle.witness_keys[0]
        witness = WitnessNode(
            witness_id="Witness-W1",
            subject_signer=signer_bundle.signer,
            witness_signer=signer_bundle.signer,
            subject_public_keys={
                SUBJECT_ID: signer_bundle.subject_public_key,
            },
            witness_private_key=witness_private,
            witness_public_keys={},
            now_ms=clock.now_ms,
        )
        witness_result = witness.process(commitment)

        disclosure_rows: list[dict[str, Any]] = []
        all_disclosures_valid = True
        total_disclosure_bytes = 0
        total_proof_items = 0
        total_generate_wall_ms = 0.0
        total_verify_wall_ms = 0.0

        for slot_index, envelope in enumerate(envelopes):
            disclosed_at_ms = envelope.t_start_ms

            generate_started_ns = time.perf_counter_ns()
            disclosure = create_disclosure(
                commitment,
                envelopes,
                slot_index=slot_index,
                disclosed_at_ms=disclosed_at_ms,
            )
            generation_wall_ms = (
                time.perf_counter_ns() - generate_started_ns
            ) / 1_000_000

            verify_started_ns = time.perf_counter_ns()
            valid = verify_disclosure(
                commitment,
                disclosure,
                enforce_slot_time=True,
            )
            verify_wall_ms = (
                time.perf_counter_ns() - verify_started_ns
            ) / 1_000_000

            disclosure_bytes = len(disclosure.to_bytes())
            proof_items = len(disclosure.merkle_proof)

            all_disclosures_valid = all_disclosures_valid and valid
            total_disclosure_bytes += disclosure_bytes
            total_proof_items += proof_items
            total_generate_wall_ms += generation_wall_ms
            total_verify_wall_ms += verify_wall_ms

            disclosure_rows.append(
                {
                    "slot_index": slot_index,
                    "valid": valid,
                    "bytes": disclosure_bytes,
                    "proof_items": proof_items,
                    "generation_wall_ms": generation_wall_ms,
                    "verification_wall_ms": verify_wall_ms,
                }
            )

        original = create_disclosure(
            commitment,
            envelopes,
            slot_index=0,
            disclosed_at_ms=envelopes[0].t_start_ms,
        )
        tampered = replace(
            original,
            envelope=replace(
                original.envelope,
                pos_min_mm=original.envelope.pos_min_mm + 1,
            ),
        )
        tampered_disclosure_rejected = not verify_disclosure(
            commitment,
            tampered,
            enforce_slot_time=True,
        )

        result = {
            "status": "PASS"
            if (
                commitment_signature_valid
                and witness_result.code is ResultCode.ACCEPT
                and witness_result.receipt is not None
                and witness_result.receipt.decision == "ACCEPTED"
                and all_disclosures_valid
                and tampered_disclosure_rejected
            )
            else "FAIL",
            "algorithm": args.algorithm,
            "subject_state": state.to_dict(),
            "slot_count": args.slots,
            "slot_ms": args.slot_ms,
            "commitment_signature_valid": commitment_signature_valid,
            "witness_result": witness_result.code.value,
            "witness_receipt_decision": (
                None
                if witness_result.receipt is None
                else witness_result.receipt.decision
            ),
            "commitment_bytes": len(canonical_json_bytes(commitment)),
            "total_disclosure_bytes": total_disclosure_bytes,
            "mean_disclosure_bytes": total_disclosure_bytes / args.slots,
            "total_proof_items": total_proof_items,
            "all_disclosures_valid": all_disclosures_valid,
            "tampered_disclosure_rejected": tampered_disclosure_rejected,
            "signer_setup_ms": signer_setup_ms,
            "commitment_create_wall_ms": commitment_create_wall_ms,
            "commitment_verify_wall_ms": commitment_verify_wall_ms,
            "proof_generation_total_wall_ms": total_generate_wall_ms,
            "proof_verification_total_wall_ms": total_verify_wall_ms,
            "disclosures": disclosure_rows,
            "total_wall_ms": (
                time.perf_counter_ns() - started_ns
            ) / 1_000_000,
            "output_json": str(output_path.resolve()),
        }

        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print("=== WTC SUMO REVEAL RESULT ===")
        print(f"Algorithm           : {args.algorithm}")
        print(f"Slots               : {args.slots}")
        print(f"Commitment valid    : {commitment_signature_valid}")
        print(f"Witness             : {witness_result.code.value}")
        print(f"Receipt decision    : {result['witness_receipt_decision']}")
        print(f"All proofs valid    : {all_disclosures_valid}")
        print(f"Tamper rejected     : {tampered_disclosure_rejected}")
        print(f"Commitment bytes    : {result['commitment_bytes']}")
        print(f"Disclosure bytes    : {total_disclosure_bytes}")
        print(f"Output              : {output_path.resolve()}")
        print(
            "WTC SUMO REVEAL: "
            + ("PASS" if result["status"] == "PASS" else "FAIL")
        )
        return 0 if result["status"] == "PASS" else 1

    except Exception as exc:
        result = {
            "status": "ERROR",
            "algorithm": args.algorithm,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "output_json": str(output_path.resolve()),
        }
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"ERROR: {type(exc).__name__}: {exc}")
        print(f"Error result written to: {output_path.resolve()}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
