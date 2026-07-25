from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter_ns
from typing import Callable

from wtc.commitment import CommitmentFactory
from wtc.crypto import Base64SignerAdapter
from wtc.crypto_aimer import AIMer128fSigner
from wtc.crypto_kpqc import HAETAESigner
from wtc.encoding import canonical_json_bytes
from wtc.models import ResultCode
from wtc.scenarios import NOW, plan
from wtc.witness import WitnessNode


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HAETAE_DLL = PROJECT_ROOT / "native" / "haetae" / "libhaetae-mode2.dll"
DEFAULT_AIMER_DLL = PROJECT_ROOT / "native" / "aimer" / "libaimer-128f.dll"


def percentile_nearest_rank(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def summarize(values_ns: list[int]) -> dict[str, float | int]:
    return {
        "samples": len(values_ns),
        "mean_us": statistics.fmean(values_ns) / 1_000,
        "median_us": statistics.median(values_ns) / 1_000,
        "stdev_us": statistics.stdev(values_ns) / 1_000 if len(values_ns) > 1 else 0.0,
        "min_us": min(values_ns) / 1_000,
        "max_us": max(values_ns) / 1_000,
        "p95_us": percentile_nearest_rank(values_ns, 0.95) / 1_000,
    }


def measure(operation: Callable[[], object], iterations: int, warmup: int) -> list[int]:
    for _ in range(warmup):
        operation()

    samples: list[int] = []
    for _ in range(iterations):
        start = perf_counter_ns()
        operation()
        samples.append(perf_counter_ns() - start)
    return samples


def load_raw_signer(algorithm: str, dll_path: Path):
    if algorithm == "haetae":
        return HAETAESigner(str(dll_path))
    if algorithm == "aimer":
        return AIMer128fSigner(dll_path)
    raise ValueError(f"unsupported algorithm: {algorithm}")


def new_witness(
    signer: Base64SignerAdapter,
    subject_public_key: bytes,
    witness_private_key: bytes,
    witness_public_key: bytes,
) -> WitnessNode:
    return WitnessNode(
        witness_id="RSU-BENCH",
        subject_signer=signer,
        witness_signer=signer,
        subject_public_keys={"Vehicle-BENCH": subject_public_key},
        witness_public_keys={"RSU-BENCH": witness_public_key},
        witness_private_key=witness_private_key,
        now_ms=lambda: NOW,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark raw KpqC and WTC processing")
    parser.add_argument("--algorithm", choices=("haetae", "aimer"), required=True)
    parser.add_argument("--dll", type=Path)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--message-size", type=int, default=256)
    args = parser.parse_args()

    if args.iterations < 2:
        raise SystemExit("--iterations must be at least 2")
    if args.warmup < 0:
        raise SystemExit("--warmup must be non-negative")
    if args.message_size < 1:
        raise SystemExit("--message-size must be positive")

    dll_path = (args.dll or (
        DEFAULT_HAETAE_DLL if args.algorithm == "haetae" else DEFAULT_AIMER_DLL
    )).resolve()
    if not dll_path.is_file():
        raise SystemExit(f"DLL not found: {dll_path}")

    raw_signer = load_raw_signer(args.algorithm, dll_path)
    signer = Base64SignerAdapter(raw_signer)

    subject_public_key, subject_private_key = signer.keygen()
    witness_public_key, witness_private_key = signer.keygen()
    raw_message = bytes((index % 251 for index in range(args.message_size)))
    raw_signature = raw_signer.sign(raw_message, subject_private_key)
    if not raw_signer.verify(raw_message, raw_signature, subject_public_key):
        raise RuntimeError("pre-benchmark signature verification failed")

    factory = CommitmentFactory(signer)
    c0 = factory.create(
        subject_id="Vehicle-BENCH",
        session_id="WTC-BENCH",
        epoch=1,
        sequence=0,
        valid_from_ms=NOW - 100,
        valid_until_ms=NOW + 10_000,
        envelopes=plan("1", "KEEP", 100_000),
        private_key=subject_private_key,
    )
    c1a = factory.create(
        subject_id="Vehicle-BENCH",
        session_id="WTC-BENCH",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=plan("2", "LEFT", 110_000),
        parent_root=c0.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=subject_private_key,
    )
    c1b = factory.create(
        subject_id="Vehicle-BENCH",
        session_id="WTC-BENCH",
        epoch=1,
        sequence=1,
        valid_from_ms=NOW,
        valid_until_ms=NOW + 10_000,
        envelopes=plan("3", "RIGHT", 110_000),
        parent_root=c0.merkle_root,
        update_reason="OBSTACLE_AVOID",
        private_key=subject_private_key,
    )

    counter = 0

    def benchmark_commitment_create():
        nonlocal counter
        counter += 1
        return factory.create(
            subject_id="Vehicle-BENCH",
            session_id=f"CREATE-{counter}",
            epoch=1,
            sequence=0,
            valid_from_ms=NOW - 100,
            valid_until_ms=NOW + 10_000,
            envelopes=plan("1", "KEEP", 100_000),
            private_key=subject_private_key,
        )

    def benchmark_initial_process():
        witness = new_witness(
            signer,
            subject_public_key,
            witness_private_key,
            witness_public_key,
        )
        result = witness.process(c0)
        if result.code is not ResultCode.ACCEPT:
            raise RuntimeError(f"unexpected initial result: {result.code}")
        return result

    def benchmark_valid_update():
        witness = new_witness(
            signer,
            subject_public_key,
            witness_private_key,
            witness_public_key,
        )
        witness.process(c0)
        result = witness.process(c1a)
        if result.code is not ResultCode.VALID_UPDATE:
            raise RuntimeError(f"unexpected update result: {result.code}")
        return result

    def benchmark_conflict():
        witness = new_witness(
            signer,
            subject_public_key,
            witness_private_key,
            witness_public_key,
        )
        witness.process(c0)
        witness.process(c1a)
        result = witness.process(c1b)
        if result.code is not ResultCode.CONFLICT or result.evidence is None:
            raise RuntimeError(f"unexpected conflict result: {result.code}")
        return result

    evidence_result = benchmark_conflict()
    evidence = evidence_result.evidence
    assert evidence is not None

    operations: dict[str, Callable[[], object]] = {
        "raw_keygen": raw_signer.keygen,
        "raw_sign": lambda: raw_signer.sign(raw_message, subject_private_key),
        "raw_verify": lambda: raw_signer.verify(
            raw_message,
            raw_signature,
            subject_public_key,
        ),
        "wtc_commitment_create": benchmark_commitment_create,
        "wtc_initial_process": benchmark_initial_process,
        "wtc_valid_update_process": benchmark_valid_update,
        "wtc_conflict_detection": benchmark_conflict,
        "evidence_json_serialize": lambda: json.dumps(
            evidence.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8"),
    }

    results: dict[str, dict[str, float | int]] = {}
    for name, operation in operations.items():
        print(f"Measuring {name}...", flush=True)
        results[name] = summarize(measure(operation, args.iterations, args.warmup))

    commitment_json = canonical_json_bytes(c0.__dict__)
    receipt = evidence.receipt_b
    if receipt is None:
        raise RuntimeError("evidence receipt is missing")
    receipt_json = canonical_json_bytes(receipt.__dict__)
    evidence_json = json.dumps(
        evidence.to_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    sizes = {
        "public_key_bytes": len(subject_public_key),
        "secret_key_bytes": len(subject_private_key),
        "raw_signature_bytes": len(raw_signature),
        "base64_signature_chars": len(c0.signature),
        "base64_signature_utf8_bytes": len(c0.signature.encode("ascii")),
        "commitment_json_bytes": len(commitment_json),
        "witness_receipt_json_bytes": len(receipt_json),
        "evidence_bundle_json_bytes": len(evidence_json),
        "trajectory_envelope_count": len(plan("1", "KEEP", 100_000)),
        "raw_message_bytes": len(raw_message),
    }

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = PROJECT_ROOT / "artifacts" / "benchmarks"
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{args.algorithm}_{timestamp}"
    json_path = output_dir / f"{stem}.json"
    csv_path = output_dir / f"{stem}.csv"

    payload = {
        "algorithm": raw_signer.algorithm_name,
        "dll": str(dll_path),
        "iterations": args.iterations,
        "warmup": args.warmup,
        "generated_at_utc": timestamp,
        "environment": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python": sys.version,
            "executable": sys.executable,
            "pid": os.getpid(),
        },
        "timings": results,
        "sizes": sizes,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    fieldnames = [
        "operation",
        "samples",
        "mean_us",
        "median_us",
        "stdev_us",
        "min_us",
        "max_us",
        "p95_us",
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for operation, summary in results.items():
            writer.writerow({"operation": operation, **summary})

    print("\n=== Timing summary (microseconds) ===")
    for operation, summary in results.items():
        print(
            f"{operation:<28} "
            f"median={summary['median_us']:>12.3f}  "
            f"mean={summary['mean_us']:>12.3f}  "
            f"p95={summary['p95_us']:>12.3f}"
        )
    print("\n=== Size summary (bytes unless noted) ===")
    for name, value in sizes.items():
        print(f"{name:<32} {value}")
    print(f"\nJSON: {json_path}")
    print(f"CSV : {csv_path}")


if __name__ == "__main__":
    main()
