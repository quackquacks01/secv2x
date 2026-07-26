from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import statistics
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "sumo" / "sweeps"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a parameter sweep for the SUMO WTC experiment."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    return parser.parse_args()


def _as_list(config: dict[str, Any], key: str, default: Any) -> list[Any]:
    value = config.get(key, default)
    if isinstance(value, list):
        return value
    return [value]


def load_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"config not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("experiment config must be a JSON object")
    return payload


def build_cases(config: dict[str, Any]) -> list[dict[str, Any]]:
    dimensions = {
        "scenario": _as_list(config, "scenarios", ["equivocation"]),
        "algorithm": _as_list(config, "algorithms", ["mock"]),
        "vehicle_count": _as_list(config, "vehicle_counts", [3]),
        "witness_count": _as_list(config, "witness_counts", [2]),
        "delay_ms": _as_list(config, "delay_ms", [0]),
        "jitter_ms": _as_list(config, "jitter_ms", [0]),
        "loss_rate": _as_list(config, "loss_rates", [0.0]),
        "duplicate_rate": _as_list(config, "duplicate_rates", [0.0]),
        "reorder_rate": _as_list(config, "reorder_rates", [0.0]),
        "gossip_ms": _as_list(config, "gossip_ms", [50]),
        "communication_range_m": _as_list(
            config,
            "communication_ranges_m",
            [None],
        ),
        "slots": _as_list(config, "slot_counts", [5]),
        "seed": _as_list(config, "seeds", [1]),
    }

    keys = list(dimensions)
    cases = [
        dict(zip(keys, values))
        for values in itertools.product(*(dimensions[key] for key in keys))
    ]
    return cases


def _percentile(values: Iterable[float], percentile: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    fraction = rank - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def flatten_result(result: dict[str, Any]) -> dict[str, Any]:
    background = result.get("background_load") or {}
    gossip = result.get("gossip_events") or {}

    row = {
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "scenario": result.get("scenario"),
        "algorithm": result.get("algorithm"),
        "seed": result.get("seed"),
        "requested_vehicle_count": result.get("requested_vehicle_count"),
        "observed_sumo_vehicle_count": result.get("observed_sumo_vehicle_count"),
        "physical_sumo_vehicle_count": result.get("physical_sumo_vehicle_count"),
        "physical_vehicle_requirement_met": result.get(
            "physical_vehicle_requirement_met"
        ),
        "vehicle_count_mode": result.get("vehicle_count_mode"),
        "witness_count": result.get("witness_count"),
        "communication_range_m": result.get("communication_range_m"),
        "reachable_witness_count": len(
            result.get("subject_reachable_witnesses") or []
        ),
        "out_of_range_direct_count": result.get(
            "out_of_range_direct_count",
            0,
        ),
        "out_of_range_gossip_count": result.get(
            "out_of_range_gossip_count",
            0,
        ),
        "slot_count": result.get("slot_count"),
        "delay_ms": result.get("delay_ms"),
        "jitter_ms": result.get("jitter_ms"),
        "loss_rate": result.get("loss_rate"),
        "duplicate_rate": result.get("duplicate_rate"),
        "reorder_rate": result.get("reorder_rate"),
        "gossip_period_ms": result.get("gossip_period_ms"),
        "observable_attack": result.get("observable_attack"),
        "conflict_detected": result.get("conflict_detected"),
        "evidence_generated": result.get("evidence_generated"),
        "evidence_count": result.get("evidence_count", 0),
        "detection_e2e_ms": result.get("detection_e2e_ms"),
        "detection_e2e_simulated_ms": result.get(
            "detection_e2e_simulated_ms",
            result.get("detection_e2e_ms"),
        ),
        "detection_logic_ms": result.get("detection_logic_ms"),
        "detection_logic_wall_ms": result.get(
            "detection_logic_wall_ms",
            result.get("detection_logic_ms"),
        ),
        "attack_to_evidence_wall_ms": result.get("attack_to_evidence_wall_ms"),
        "total_wall_ms": result.get("total_wall_ms"),
        "signer_setup_ms": result.get("signer_setup_ms"),
        "background_commitments": background.get("background_commitments"),
        "background_accepted": background.get("accepted"),
        "background_elapsed_ms": background.get("elapsed_ms"),
        "background_throughput_per_sec": background.get(
            "throughput_commitments_per_sec"
        ),
        "background_peak_memory_kib": background.get("peak_memory_kib"),
        "gossip_sent": gossip.get("sent", 0),
        "gossip_delivered": gossip.get("delivered", 0),
        "gossip_dropped": gossip.get("dropped", 0),
        "gossip_duplicated": gossip.get("duplicated", 0),
        "error_type": result.get("error_type"),
        "error": result.get("error"),
        "result_file": result.get("_result_file"),
    }
    return row


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    group_keys = (
        "scenario",
        "algorithm",
        "requested_vehicle_count",
        "witness_count",
        "slot_count",
        "delay_ms",
        "jitter_ms",
        "loss_rate",
        "duplicate_rate",
        "reorder_rate",
        "gossip_period_ms",
        "communication_range_m",
    )
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(key) for key in group_keys)].append(row)

    summaries: list[dict[str, Any]] = []
    for key_values, group in groups.items():
        record = dict(zip(group_keys, key_values))
        attack_rows = [
            row for row in group if row.get("scenario") == "equivocation"
        ]
        observable_rows = [
            row for row in attack_rows if row.get("observable_attack") is True
        ]
        detected_rows = [
            row for row in attack_rows if row.get("conflict_detected") is True
        ]
        detected_observable_rows = [
            row
            for row in observable_rows
            if row.get("conflict_detected") is True
        ]
        e2e_values = [
            float(row["detection_e2e_simulated_ms"])
            for row in detected_rows
            if row.get("detection_e2e_simulated_ms") is not None
        ]
        logic_values = [
            float(row["detection_logic_wall_ms"])
            for row in detected_rows
            if row.get("detection_logic_wall_ms") is not None
        ]
        attack_wall_values = [
            float(row["attack_to_evidence_wall_ms"])
            for row in detected_rows
            if row.get("attack_to_evidence_wall_ms") is not None
        ]
        throughput_values = [
            float(row["background_throughput_per_sec"])
            for row in group
            if row.get("background_throughput_per_sec") is not None
        ]
        memory_values = [
            float(row["background_peak_memory_kib"])
            for row in group
            if row.get("background_peak_memory_kib") is not None
        ]

        record.update(
            {
                "runs": len(group),
                "error_runs": sum(
                    1 for row in group if row.get("status") == "ERROR"
                ),
                "attack_runs": len(attack_rows),
                "observable_attack_runs": len(observable_rows),
                "detected_runs": len(detected_rows),
                "detection_rate_total": (
                    None
                    if not attack_rows
                    else len(detected_rows) / len(attack_rows)
                ),
                "detection_rate_observable": (
                    None
                    if not observable_rows
                    else len(detected_observable_rows) / len(observable_rows)
                ),
                "mean_detection_e2e_ms": (
                    statistics.fmean(e2e_values) if e2e_values else None
                ),
                "p95_detection_e2e_ms": _percentile(e2e_values, 0.95),
                "mean_detection_e2e_simulated_ms": (
                    statistics.fmean(e2e_values) if e2e_values else None
                ),
                "p95_detection_e2e_simulated_ms": _percentile(e2e_values, 0.95),
                "mean_detection_logic_ms": (
                    statistics.fmean(logic_values) if logic_values else None
                ),
                "p95_detection_logic_ms": _percentile(logic_values, 0.95),
                "mean_detection_logic_wall_ms": (
                    statistics.fmean(logic_values) if logic_values else None
                ),
                "p95_detection_logic_wall_ms": _percentile(logic_values, 0.95),
                "mean_attack_to_evidence_wall_ms": (
                    statistics.fmean(attack_wall_values)
                    if attack_wall_values
                    else None
                ),
                "p95_attack_to_evidence_wall_ms": _percentile(
                    attack_wall_values,
                    0.95,
                ),
                "mean_background_throughput_per_sec": (
                    statistics.fmean(throughput_values)
                    if throughput_values
                    else None
                ),
                "mean_background_peak_memory_kib": (
                    statistics.fmean(memory_values)
                    if memory_values
                    else None
                ),
                "total_evidence_count": sum(
                    int(row.get("evidence_count") or 0) for row in group
                ),
            }
        )
        summaries.append(record)

    summaries.sort(
        key=lambda row: tuple(
            str(row.get(key, "")) for key in group_keys
        )
    )
    return summaries


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)



def _resolve_path(value: str | Path, project_root: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def ensure_physical_scenario(
    *,
    vehicle_count: int,
    witness_count: int,
    config: dict[str, Any],
    cache: dict[tuple[int, int], Path],
) -> Path:
    key = (vehicle_count, witness_count)
    if key in cache:
        return cache[key]

    scenario_root = _resolve_path(
        config.get(
            "scalable_scenario_root",
            PROJECT_ROOT
            / "simulation"
            / "sumo"
            / "scenarios"
            / "scalable",
        ),
        PROJECT_ROOT,
    )
    output_dir = scenario_root / f"N{vehicle_count}_W{witness_count}"
    sumo_config = output_dir / "scalable.sumocfg"
    network_file = output_dir / "scalable.net.xml"
    manifest_file = output_dir / "scenario_manifest.json"

    regenerate = bool(config.get("regenerate_scenarios", False))
    if regenerate or not (
        sumo_config.is_file()
        and network_file.is_file()
        and manifest_file.is_file()
    ):
        command = [
            sys.executable,
            "-m",
            "simulation.sumo.generators.generate_scalable_scenario",
            "--vehicle-count",
            str(vehicle_count),
            "--witness-count",
            str(witness_count),
            "--output-dir",
            str(output_dir),
            "--lane-count",
            str(int(config.get("lane_count", 4))),
            "--witness-spacing-m",
            str(float(config.get("witness_spacing_m", 30.0))),
            "--background-spacing-m",
            str(float(config.get("background_spacing_m", 15.0))),
            "--speed-mps",
            str(float(config.get("speed_mps", 13.89))),
        ]
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "failed to generate physical SUMO scenario "
                f"N={vehicle_count}, W={witness_count}"
            )

    cache[key] = sumo_config.resolve()
    return cache[key]


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    cases = build_cases(config)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = (
        args.output_dir
        or DEFAULT_ARTIFACT_ROOT / f"{args.config.stem}_{stamp}"
    )
    run_dir = output_dir / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)

    sumo_config = Path(
        config.get(
            "sumo_config",
            PROJECT_ROOT
            / "simulation"
            / "sumo"
            / "scenarios"
            / "minimal"
            / "minimal.sumocfg",
        )
    )
    if not sumo_config.is_absolute():
        sumo_config = (PROJECT_ROOT / sumo_config).resolve()

    common = {
        "steps": int(config.get("steps", 20)),
        "activation_wait_steps": int(
            config.get("activation_wait_steps", 500)
        ),
        "slot_ms": int(config.get("slot_ms", 200)),
        "allow_no_conflict": bool(config.get("allow_no_conflict", True)),
        "generate_physical_scenarios": bool(
            config.get("generate_physical_scenarios", False)
        ),
        "require_physical_vehicles": bool(
            config.get("require_physical_vehicles", False)
        ),
        "haetae_dll": str(
            config.get(
                "haetae_dll",
                PROJECT_ROOT
                / "native"
                / "haetae"
                / "libhaetae-mode2.dll",
            )
        ),
        "aimer_dll": str(
            config.get(
                "aimer_dll",
                PROJECT_ROOT
                / "native"
                / "aimer"
                / "libaimer-128f.dll",
            )
        ),
    }

    print(f"Config      : {args.config.resolve()}")
    print(f"Cases       : {len(cases)}")
    print(f"Output      : {output_dir.resolve()}")
    print(
        "SUMO mode   : "
        + (
            "generated physical scenarios"
            if common["generate_physical_scenarios"]
            else str(sumo_config)
        )
    )

    if args.dry_run:
        for index, case in enumerate(cases, start=1):
            print(f"{index:04d}: {case}")
        print("SWEEP DRY RUN: PASS")
        return 0

    results: list[dict[str, Any]] = []
    failures = 0
    physical_scenario_cache: dict[tuple[int, int], Path] = {}

    for index, case in enumerate(cases, start=1):
        result_path = run_dir / f"run_{index:05d}.json"

        if common["generate_physical_scenarios"]:
            case_sumo_config = ensure_physical_scenario(
                vehicle_count=int(case["vehicle_count"]),
                witness_count=int(case["witness_count"]),
                config=config,
                cache=physical_scenario_cache,
            )
        else:
            case_sumo_config = sumo_config

        command = [
            sys.executable,
            "-m",
            "simulation.sumo.controllers.run_wtc_sumo",
            "--scenario",
            str(case["scenario"]),
            "--algorithm",
            str(case["algorithm"]),
            "--sumo-config",
            str(case_sumo_config),
            "--steps",
            str(common["steps"]),
            "--activation-wait-steps",
            str(common["activation_wait_steps"]),
            "--slots",
            str(case["slots"]),
            "--slot-ms",
            str(common["slot_ms"]),
            "--vehicle-count",
            str(case["vehicle_count"]),
            "--witness-count",
            str(case["witness_count"]),
            "--delay-ms",
            str(case["delay_ms"]),
            "--jitter-ms",
            str(case["jitter_ms"]),
            "--loss-rate",
            str(case["loss_rate"]),
            "--duplicate-rate",
            str(case["duplicate_rate"]),
            "--reorder-rate",
            str(case["reorder_rate"]),
            "--gossip-ms",
            str(case["gossip_ms"]),
        ]
        if case["communication_range_m"] is not None:
            command.extend(
                [
                    "--communication-range-m",
                    str(case["communication_range_m"]),
                ]
            )
        if common["require_physical_vehicles"]:
            command.append("--require-physical-vehicles")

        command.extend(
            [
            "--seed",
            str(case["seed"]),
            "--haetae-dll",
            common["haetae_dll"],
            "--aimer-dll",
            common["aimer_dll"],
            "--output-json",
            str(result_path),
            ]
        )
        if common["allow_no_conflict"]:
            command.append("--allow-no-conflict")

        print(
            f"\n[{index}/{len(cases)}] "
            f"{case['scenario']} {case['algorithm']} "
            f"N={case['vehicle_count']} W={case['witness_count']} "
            f"range={case['communication_range_m']} "
            f"delay={case['delay_ms']} loss={case['loss_rate']} "
            f"seed={case['seed']}"
        )
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=False,
        )

        if not result_path.exists():
            result = {
                "status": "ERROR",
                "error_type": "MissingResultFile",
                "error": f"runner did not create {result_path}",
            }
        else:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        result["_result_file"] = str(result_path.resolve())
        results.append(result)

        if completed.returncode != 0 or result.get("status") == "ERROR":
            failures += 1
            if args.stop_on_error:
                break

    rows = [flatten_result(result) for result in results]
    summaries = summarize(rows)

    raw_json = output_dir / "raw_results.json"
    raw_csv = output_dir / "raw_results.csv"
    summary_json = output_dir / "summary.json"
    summary_csv = output_dir / "summary.csv"
    manifest_json = output_dir / "manifest.json"

    raw_json.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(raw_csv, rows)
    summary_json.write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(summary_csv, summaries)
    manifest_json.write_text(
        json.dumps(
            {
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "config": str(args.config.resolve()),
                "case_count": len(cases),
                "completed_count": len(results),
                "failure_count": failures,
                "generate_physical_scenarios": common[
                    "generate_physical_scenarios"
                ],
                "require_physical_vehicles": common[
                    "require_physical_vehicles"
                ],
                "raw_json": str(raw_json.resolve()),
                "raw_csv": str(raw_csv.resolve()),
                "summary_json": str(summary_json.resolve()),
                "summary_csv": str(summary_csv.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n=== SWEEP RESULT ===")
    print(f"Completed : {len(results)}/{len(cases)}")
    print(f"Failures  : {failures}")
    print(f"Raw CSV   : {raw_csv.resolve()}")
    print(f"Summary   : {summary_csv.resolve()}")
    print(
        "SUMO WTC SWEEP: "
        + ("PASS" if failures == 0 else "COMPLETED WITH ERRORS")
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
