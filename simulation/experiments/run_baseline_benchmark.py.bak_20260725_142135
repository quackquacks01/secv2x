from __future__ import annotations

import argparse
import base64
import binascii
import csv
import json
import math
import statistics
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.wtc.commitment import CommitmentFactory, commitment_message
from src.wtc.crypto import Signer
from src.wtc.disclosure import create_disclosure, verify_disclosure
from src.wtc.encoding import canonical_json_bytes
from src.wtc.models import ResultCode, TrajectoryEnvelope
from src.wtc.witness import WitnessNode

from simulation.sumo.controllers.run_wtc_sumo import (
    MutableClock,
    SignerBundle,
    VehicleState,
    create_signer_bundle,
    state_to_envelopes,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = (
    PROJECT_ROOT / "artifacts" / "baseline_benchmark"
)
BASELINE_SLOT_DOMAIN = b"KPQC-WTC-BASELINE-SLOT-V1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare Baseline A, Baseline B and Proposed WTC session "
            "communication and processing costs."
        )
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"config not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("config must be a JSON object")
    return payload


def percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * fraction
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return

    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def signature_raw_bytes(signature: str, algorithm: str) -> int:
    if algorithm == "mock":
        try:
            return len(bytes.fromhex(signature))
        except ValueError:
            return len(signature.encode("utf-8"))

    try:
        return len(base64.b64decode(signature, validate=True))
    except (binascii.Error, ValueError):
        return len(signature.encode("utf-8"))


def synthetic_state() -> VehicleState:
    return VehicleState(
        vehicle_id="Vehicle-A",
        simulation_time_ms=1_000_000,
        x_m=0.0,
        y_m=0.0,
        lane_position_m=100.0,
        speed_mps=13.89,
        acceleration_mps2=0.0,
        lane_id="E0_0",
        road_id="E0",
        route_edges=("E0",),
        route_index=0,
    )


def baseline_slot_body(
    envelope: TrajectoryEnvelope,
    *,
    slot_count: int,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "subject_id": "Vehicle-A",
        "session_id": "BASELINE-SESSION-001",
        "epoch": 1,
        "sequence": 0,
        "slot_count": slot_count,
        "slot_index": envelope.segment_index,
        "envelope": asdict(envelope),
    }


def create_baseline_a_messages(
    signer: Signer,
    *,
    private_key: bytes,
    public_key: bytes,
    envelopes: list[TrajectoryEnvelope],
) -> tuple[list[dict[str, Any]], float, float, bool]:
    messages: list[dict[str, Any]] = []

    sign_started_ns = time.perf_counter_ns()
    for envelope in envelopes:
        body = baseline_slot_body(
            envelope,
            slot_count=len(envelopes),
        )
        signed_bytes = BASELINE_SLOT_DOMAIN + canonical_json_bytes(body)
        signature = signer.sign(signed_bytes, private_key)
        messages.append(
            {
                "body": body,
                "signature_algorithm": signer.algorithm_name,
                "signature": signature,
            }
        )
    sign_wall_ms = (
        time.perf_counter_ns() - sign_started_ns
    ) / 1_000_000

    verify_started_ns = time.perf_counter_ns()
    valid = all(
        signer.verify(
            BASELINE_SLOT_DOMAIN
            + canonical_json_bytes(message["body"]),
            message["signature"],
            public_key,
        )
        for message in messages
    )
    verify_wall_ms = (
        time.perf_counter_ns() - verify_started_ns
    ) / 1_000_000

    return messages, sign_wall_ms, verify_wall_ms, valid


def build_witnesses(
    signer_bundle: SignerBundle,
    *,
    witness_count: int,
    clock: MutableClock,
) -> list[WitnessNode]:
    public_registry = {
        f"Witness-W{index + 1}": signer_bundle.witness_keys[index][0]
        for index in range(witness_count)
    }
    witnesses: list[WitnessNode] = []

    for index in range(witness_count):
        witness_id = f"Witness-W{index + 1}"
        _, private_key = signer_bundle.witness_keys[index]
        witnesses.append(
            WitnessNode(
                witness_id=witness_id,
                subject_signer=signer_bundle.signer,
                witness_signer=signer_bundle.signer,
                subject_public_keys={
                    "Vehicle-A": signer_bundle.subject_public_key,
                },
                witness_private_key=private_key,
                witness_public_keys={
                    peer_id: peer_key
                    for peer_id, peer_key in public_registry.items()
                    if peer_id != witness_id
                },
                now_ms=clock.now_ms,
            )
        )
    return witnesses


def run_repetition(
    *,
    algorithm: str,
    slot_count: int,
    witness_count: int,
    signer_bundle: SignerBundle,
    slot_ms: int,
) -> dict[str, Any]:
    state = synthetic_state()
    envelopes = state_to_envelopes(
        state,
        slot_count=slot_count,
        slot_ms=slot_ms,
    )

    # Baseline A: every slot carries an independent KpqC signature.
    (
        baseline_a_messages,
        baseline_a_sign_wall_ms,
        baseline_a_verify_wall_ms,
        baseline_a_valid,
    ) = create_baseline_a_messages(
        signer_bundle.signer,
        private_key=signer_bundle.subject_private_key,
        public_key=signer_bundle.subject_public_key,
        envelopes=envelopes,
    )
    baseline_a_unique_bytes = sum(
        len(canonical_json_bytes(message))
        for message in baseline_a_messages
    )
    baseline_a_network_tx_bytes = (
        baseline_a_unique_bytes * witness_count
    )

    # Baseline B and Proposed share one signed Merkle commitment and
    # per-slot disclosures.
    factory = CommitmentFactory(signer_bundle.signer)
    commitment_started_ns = time.perf_counter_ns()
    commitment = factory.create(
        subject_id="Vehicle-A",
        session_id="BASELINE-SESSION-001",
        epoch=1,
        sequence=0,
        valid_from_ms=state.simulation_time_ms,
        valid_until_ms=(
            state.simulation_time_ms
            + slot_count * slot_ms
            + 5_000
        ),
        envelopes=envelopes,
        private_key=signer_bundle.subject_private_key,
    )
    commitment_sign_wall_ms = (
        time.perf_counter_ns() - commitment_started_ns
    ) / 1_000_000

    commitment_verify_started_ns = time.perf_counter_ns()
    commitment_signature_valid = signer_bundle.signer.verify(
        commitment_message(commitment),
        commitment.signature,
        signer_bundle.subject_public_key,
    )
    commitment_verify_wall_ms = (
        time.perf_counter_ns() - commitment_verify_started_ns
    ) / 1_000_000

    proof_generate_started_ns = time.perf_counter_ns()
    disclosures = [
        create_disclosure(
            commitment,
            envelopes,
            slot_index=index,
            disclosed_at_ms=envelopes[index].t_start_ms,
        )
        for index in range(slot_count)
    ]
    proof_generation_wall_ms = (
        time.perf_counter_ns() - proof_generate_started_ns
    ) / 1_000_000

    proof_verify_started_ns = time.perf_counter_ns()
    disclosures_valid = all(
        verify_disclosure(
            commitment,
            disclosure,
            enforce_slot_time=True,
        )
        for disclosure in disclosures
    )
    proof_verification_wall_ms = (
        time.perf_counter_ns() - proof_verify_started_ns
    ) / 1_000_000

    commitment_bytes = len(canonical_json_bytes(commitment))
    disclosure_total_bytes = sum(
        len(disclosure.to_bytes())
        for disclosure in disclosures
    )
    baseline_b_unique_bytes = commitment_bytes + disclosure_total_bytes
    baseline_b_network_tx_bytes = (
        baseline_b_unique_bytes * witness_count
    )

    clock = MutableClock(state.simulation_time_ms)
    witnesses = build_witnesses(
        signer_bundle,
        witness_count=witness_count,
        clock=clock,
    )

    receipt_started_ns = time.perf_counter_ns()
    receipt_results = [
        witness.process(commitment)
        for witness in witnesses
    ]
    receipt_processing_wall_ms = (
        time.perf_counter_ns() - receipt_started_ns
    ) / 1_000_000

    receipts = [
        result.receipt
        for result in receipt_results
        if result.receipt is not None
    ]
    receipts_valid = (
        len(receipts) == witness_count
        and all(
            result.code is ResultCode.ACCEPT
            and result.receipt is not None
            and result.receipt.decision == "ACCEPTED"
            for result in receipt_results
        )
    )
    receipt_total_bytes = sum(
        len(canonical_json_bytes(receipt))
        for receipt in receipts
    )

    gossip_records: list[dict[str, Any]] = []
    gossip_verify_wall_ms = 0.0
    gossip_valid = True

    for sender_index, sender in enumerate(witnesses):
        receipt = receipts[sender_index]
        for receiver_index, receiver in enumerate(witnesses):
            if sender_index == receiver_index:
                continue
            gossip_records.append(
                {
                    "sender_id": sender.witness_id,
                    "receiver_id": receiver.witness_id,
                    "commitment": asdict(commitment),
                    "receipt": asdict(receipt),
                }
            )
            started_ns = time.perf_counter_ns()
            result = receiver.process_gossip(
                commitment,
                receipt,
                None,
            )
            gossip_verify_wall_ms += (
                time.perf_counter_ns() - started_ns
            ) / 1_000_000
            gossip_valid = gossip_valid and result.code in {
                ResultCode.DUPLICATE,
                ResultCode.ACCEPT,
            }

    gossip_total_bytes = sum(
        len(canonical_json_bytes(record))
        for record in gossip_records
    )
    proposed_unique_bytes = (
        baseline_b_unique_bytes
        + receipt_total_bytes
        + gossip_total_bytes
    )
    proposed_network_tx_bytes = (
        baseline_b_network_tx_bytes
        + receipt_total_bytes
        + gossip_total_bytes
    )

    baseline_a_raw_signature_bytes = sum(
        signature_raw_bytes(
            message["signature"],
            algorithm,
        )
        for message in baseline_a_messages
    )
    commitment_raw_signature_bytes = signature_raw_bytes(
        commitment.signature,
        algorithm,
    )
    witness_raw_signature_bytes = sum(
        signature_raw_bytes(receipt.signature, algorithm)
        for receipt in receipts
    )

    return {
        "algorithm": algorithm,
        "slot_count": slot_count,
        "witness_count": witness_count,
        "slot_ms": slot_ms,
        "baseline_a_valid": baseline_a_valid,
        "commitment_signature_valid": commitment_signature_valid,
        "disclosures_valid": disclosures_valid,
        "receipts_valid": receipts_valid,
        "gossip_valid": gossip_valid,
        "baseline_a_subject_signature_count": slot_count,
        "baseline_b_subject_signature_count": 1,
        "proposed_subject_signature_count": 1,
        "proposed_witness_signature_count": witness_count,
        "proposed_gossip_message_count": len(gossip_records),
        "baseline_a_raw_signature_bytes": baseline_a_raw_signature_bytes,
        "baseline_b_raw_signature_bytes": commitment_raw_signature_bytes,
        "proposed_raw_signature_bytes": (
            commitment_raw_signature_bytes
            + witness_raw_signature_bytes
        ),
        "commitment_bytes": commitment_bytes,
        "disclosure_total_bytes": disclosure_total_bytes,
        "receipt_total_bytes": receipt_total_bytes,
        "gossip_total_bytes": gossip_total_bytes,
        "baseline_a_unique_bytes": baseline_a_unique_bytes,
        "baseline_b_unique_bytes": baseline_b_unique_bytes,
        "proposed_unique_bytes": proposed_unique_bytes,
        "baseline_a_network_tx_bytes": baseline_a_network_tx_bytes,
        "baseline_b_network_tx_bytes": baseline_b_network_tx_bytes,
        "proposed_network_tx_bytes": proposed_network_tx_bytes,
        "baseline_b_vs_a_network_reduction_pct": (
            (
                baseline_a_network_tx_bytes
                - baseline_b_network_tx_bytes
            )
            / baseline_a_network_tx_bytes
            * 100
        ),
        "proposed_vs_a_network_reduction_pct": (
            (
                baseline_a_network_tx_bytes
                - proposed_network_tx_bytes
            )
            / baseline_a_network_tx_bytes
            * 100
        ),
        "baseline_a_sign_wall_ms": baseline_a_sign_wall_ms,
        "baseline_a_verify_wall_ms": baseline_a_verify_wall_ms,
        "commitment_sign_wall_ms": commitment_sign_wall_ms,
        "commitment_verify_wall_ms": commitment_verify_wall_ms,
        "proof_generation_wall_ms": proof_generation_wall_ms,
        "proof_verification_wall_ms": proof_verification_wall_ms,
        "receipt_processing_wall_ms": receipt_processing_wall_ms,
        "gossip_verification_wall_ms": gossip_verify_wall_ms,
        "baseline_a_equivocation_detection_capable": False,
        "baseline_b_equivocation_detection_capable": False,
        "proposed_equivocation_detection_capable": True,
    }


def summarize(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[
        tuple[str, int, int],
        list[dict[str, Any]],
    ] = {}
    for row in rows:
        key = (
            str(row["algorithm"]),
            int(row["slot_count"]),
            int(row["witness_count"]),
        )
        groups.setdefault(key, []).append(row)

    summaries: list[dict[str, Any]] = []
    metric_names = [
        "baseline_a_unique_bytes",
        "baseline_b_unique_bytes",
        "proposed_unique_bytes",
        "baseline_a_network_tx_bytes",
        "baseline_b_network_tx_bytes",
        "proposed_network_tx_bytes",
        "baseline_b_vs_a_network_reduction_pct",
        "proposed_vs_a_network_reduction_pct",
        "baseline_a_sign_wall_ms",
        "baseline_a_verify_wall_ms",
        "commitment_sign_wall_ms",
        "commitment_verify_wall_ms",
        "proof_generation_wall_ms",
        "proof_verification_wall_ms",
        "receipt_processing_wall_ms",
        "gossip_verification_wall_ms",
    ]

    for (algorithm, slot_count, witness_count), group in sorted(
        groups.items()
    ):
        record: dict[str, Any] = {
            "algorithm": algorithm,
            "slot_count": slot_count,
            "witness_count": witness_count,
            "runs": len(group),
            "all_valid": all(
                bool(row["baseline_a_valid"])
                and bool(row["commitment_signature_valid"])
                and bool(row["disclosures_valid"])
                and bool(row["receipts_valid"])
                and bool(row["gossip_valid"])
                for row in group
            ),
            "baseline_a_subject_signature_count": slot_count,
            "baseline_b_subject_signature_count": 1,
            "proposed_subject_signature_count": 1,
            "proposed_witness_signature_count": witness_count,
            "proposed_gossip_message_count": (
                witness_count * max(0, witness_count - 1)
            ),
        }

        for metric in metric_names:
            values = [float(row[metric]) for row in group]
            record[f"mean_{metric}"] = statistics.fmean(values)
            record[f"median_{metric}"] = statistics.median(values)
            record[f"p95_{metric}"] = percentile(values, 0.95)

        summaries.append(record)

    return summaries


def main() -> int:
    args = parse_args()
    config = load_config(args.config)

    algorithms = list(config.get("algorithms", ["mock"]))
    slot_counts = [
        int(value)
        for value in config.get("slot_counts", [5])
    ]
    witness_counts = [
        int(value)
        for value in config.get("witness_counts", [1])
    ]
    warmups = int(config.get("warmups", 0))
    repetitions = int(config.get("repetitions", 1))
    slot_ms = int(config.get("slot_ms", 200))

    if (
        not algorithms
        or not slot_counts
        or not witness_counts
        or repetitions <= 0
        or warmups < 0
        or slot_ms <= 0
    ):
        raise ValueError("invalid benchmark configuration")

    cases = [
        (algorithm, slot_count, witness_count)
        for algorithm in algorithms
        for slot_count in slot_counts
        for witness_count in witness_counts
    ]

    print(f"Config      : {args.config.resolve()}")
    print(f"Cases       : {len(cases)}")
    print(f"Warmups     : {warmups}")
    print(f"Repetitions : {repetitions}")

    if args.dry_run:
        for index, case in enumerate(cases, start=1):
            print(f"{index:03d}: {case}")
        print("BASELINE BENCHMARK DRY RUN: PASS")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = (
        args.output_dir
        or DEFAULT_OUTPUT_ROOT / f"{args.config.stem}_{stamp}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    setup_rows: list[dict[str, Any]] = []
    failures = 0

    max_witness_count = max(witness_counts)

    for algorithm in algorithms:
        setup_started_ns = time.perf_counter_ns()
        signer_bundle = create_signer_bundle(
            algorithm,
            witness_count=max_witness_count,
            haetae_dll=Path(
                config.get(
                    "haetae_dll",
                    "native/haetae/libhaetae-mode2.dll",
                )
            ),
            aimer_dll=Path(
                config.get(
                    "aimer_dll",
                    "native/aimer/libaimer-128f.dll",
                )
            ),
        )
        setup_ms = (
            time.perf_counter_ns() - setup_started_ns
        ) / 1_000_000
        setup_rows.append(
            {
                "algorithm": algorithm,
                "signer_setup_ms": setup_ms,
                "generated_subject_keypairs": 1,
                "generated_witness_keypairs": max_witness_count,
            }
        )

        algorithm_cases = [
            case
            for case in cases
            if case[0] == algorithm
        ]

        for case_index, (
            _,
            slot_count,
            witness_count,
        ) in enumerate(algorithm_cases, start=1):
            print(
                f"\n[{algorithm} {case_index}/{len(algorithm_cases)}] "
                f"slots={slot_count} witnesses={witness_count}"
            )

            for _ in range(warmups):
                run_repetition(
                    algorithm=algorithm,
                    slot_count=slot_count,
                    witness_count=witness_count,
                    signer_bundle=signer_bundle,
                    slot_ms=slot_ms,
                )

            for repetition in range(1, repetitions + 1):
                try:
                    row = run_repetition(
                        algorithm=algorithm,
                        slot_count=slot_count,
                        witness_count=witness_count,
                        signer_bundle=signer_bundle,
                        slot_ms=slot_ms,
                    )
                    row["repetition"] = repetition
                    row["status"] = (
                        "PASS"
                        if (
                            row["baseline_a_valid"]
                            and row["commitment_signature_valid"]
                            and row["disclosures_valid"]
                            and row["receipts_valid"]
                            and row["gossip_valid"]
                        )
                        else "FAIL"
                    )
                    if row["status"] != "PASS":
                        failures += 1
                    rows.append(row)
                except Exception as exc:
                    failures += 1
                    rows.append(
                        {
                            "status": "ERROR",
                            "algorithm": algorithm,
                            "slot_count": slot_count,
                            "witness_count": witness_count,
                            "repetition": repetition,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        }
                    )

    valid_rows = [
        row
        for row in rows
        if row.get("status") == "PASS"
    ]
    summaries = summarize(valid_rows)

    raw_json = output_dir / "raw_results.json"
    raw_csv = output_dir / "raw_results.csv"
    summary_json = output_dir / "summary.json"
    summary_csv = output_dir / "summary.csv"
    setup_json = output_dir / "signer_setup.json"
    manifest_json = output_dir / "manifest.json"

    raw_json.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(raw_csv, rows)
    summary_json.write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(summary_csv, summaries)
    setup_json.write_text(
        json.dumps(setup_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    manifest_json.write_text(
        json.dumps(
            {
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "config": str(args.config.resolve()),
                "case_count": len(cases),
                "warmups": warmups,
                "repetitions": repetitions,
                "expected_run_count": len(cases) * repetitions,
                "completed_run_count": len(rows),
                "failure_count": failures,
                "communication_accounting": {
                    "unique_bytes": (
                        "one serialized copy of each protocol object"
                    ),
                    "network_tx_bytes": (
                        "subject messages multiplied by witness recipients, "
                        "plus witness receipts and one full all-to-all "
                        "gossip round carrying commitment plus receipt"
                    ),
                    "gossip_topology": "one_round_all_to_all",
                },
                "raw_csv": str(raw_csv.resolve()),
                "summary_csv": str(summary_csv.resolve()),
                "signer_setup_json": str(setup_json.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n=== BASELINE BENCHMARK RESULT ===")
    print(f"Completed : {len(rows)}/{len(cases) * repetitions}")
    print(f"Failures  : {failures}")
    print(f"Raw CSV   : {raw_csv.resolve()}")
    print(f"Summary   : {summary_csv.resolve()}")
    print(
        "BASELINE BENCHMARK: "
        + ("PASS" if failures == 0 else "COMPLETED WITH ERRORS")
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
