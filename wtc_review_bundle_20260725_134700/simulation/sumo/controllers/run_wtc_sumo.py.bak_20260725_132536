from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import os
import random
import shutil
import statistics
import sys
import time
import tracemalloc
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from simulation.network.emulator import GossipNetworkEmulator
from src.wtc.commitment import CommitmentFactory
from src.wtc.crypto import Base64SignerAdapter, MockHMACSigner, Signer
from src.wtc.models import (
    Commitment,
    EvidenceBundle,
    ProcessResult,
    ResultCode,
    TrajectoryEnvelope,
    WitnessReceipt,
)
from src.wtc.witness import WitnessNode


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SUMO_CONFIG = (
    PROJECT_ROOT
    / "simulation"
    / "sumo"
    / "scenarios"
    / "minimal"
    / "minimal.sumocfg"
)
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "sumo"

SUBJECT_ID = "Vehicle-A"
SESSION_ID = "SUMO-MERGE-001"

MOCK_SUBJECT_KEY = b"sumo-subject-key"
MOCK_WITNESS_KEYS = {
    index: f"sumo-witness-key-{index}".encode("utf-8")
    for index in range(1, 33)
}


@dataclass
class MutableClock:
    value_ms: int = 0

    def now_ms(self) -> int:
        return self.value_ms

    def set(self, value_ms: int) -> None:
        self.value_ms = int(value_ms)


@dataclass(frozen=True)
class VehicleState:
    vehicle_id: str
    simulation_time_ms: int
    x_m: float
    y_m: float
    lane_position_m: float
    speed_mps: float
    acceleration_mps2: float
    lane_id: str
    road_id: str
    route_edges: tuple[str, ...] = ()
    route_index: int = -1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DirectDelivery:
    receiver_id: str
    sent_at_ms: int
    delivered_at_ms: int | None
    dropped: bool
    result: ProcessResult | None
    processing_wall_ms: float | None = None
    in_range: bool = True
    distance_m: float | None = None
    drop_reason: str | None = None


@dataclass
class SignerBundle:
    signer: Signer
    subject_public_key: bytes
    subject_private_key: bytes
    witness_keys: list[tuple[bytes, bytes]]


@dataclass
class DetectionRecord:
    witness_id: str
    detected_at_ms: int
    result: ProcessResult
    logic_wall_ms: float
    detected_wall_ns: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the KpqC WTC protocol over a minimal SUMO/TraCI scenario "
            "with asynchronous Gossip network effects."
        )
    )
    parser.add_argument(
        "--scenario",
        choices=("state", "envelope", "normal", "equivocation"),
        default="equivocation",
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
    parser.add_argument("--vehicle-count", type=int, default=3)
    parser.add_argument("--witness-count", type=int, default=2)
    parser.add_argument("--delay-ms", type=int, default=0)
    parser.add_argument("--jitter-ms", type=int, default=0)
    parser.add_argument("--loss-rate", type=float, default=0.0)
    parser.add_argument("--duplicate-rate", type=float, default=0.0)
    parser.add_argument("--reorder-rate", type=float, default=0.0)
    parser.add_argument("--gossip-ms", type=int, default=50)
    parser.add_argument(
        "--communication-range-m",
        type=float,
        default=None,
        help=(
            "Maximum Euclidean distance for Subject-to-Witness and "
            "Witness-to-Witness delivery. Omit for unlimited range."
        ),
    )
    parser.add_argument(
        "--require-physical-vehicles",
        action="store_true",
        help=(
            "Fail unless the active SUMO snapshot contains at least "
            "--vehicle-count vehicles and every requested Witness-W* vehicle."
        ),
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--print-state", action="store_true")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--evidence-json", type=Path)
    parser.add_argument(
        "--allow-no-conflict",
        action="store_true",
        help=(
            "Return exit code 0 even when an attack is not detected. "
            "Use this for packet-loss sweeps."
        ),
    )
    parser.add_argument(
        "--haetae-dll",
        type=Path,
        default=PROJECT_ROOT / "native" / "haetae" / "libhaetae-mode2.dll",
    )
    parser.add_argument(
        "--aimer-dll",
        type=Path,
        default=PROJECT_ROOT / "native" / "aimer" / "libaimer-128f.dll",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.steps <= 0:
        raise ValueError("steps must be positive")
    if args.slots <= 0:
        raise ValueError("slots must be positive")
    if args.slot_ms <= 0:
        raise ValueError("slot-ms must be positive")
    if args.vehicle_count <= 0:
        raise ValueError("vehicle-count must be positive")
    if args.witness_count <= 0:
        raise ValueError("witness-count must be positive")
    for name in ("loss_rate", "duplicate_rate", "reorder_rate"):
        value = getattr(args, name)
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name.replace('_', '-')} must be between 0 and 1")
    for name in ("delay_ms", "jitter_ms", "gossip_ms"):
        if getattr(args, name) < 0:
            raise ValueError(f"{name.replace('_', '-')} must be non-negative")
    if (
        args.communication_range_m is not None
        and args.communication_range_m <= 0
    ):
        raise ValueError("communication-range-m must be positive")


def _load_traci():
    try:
        import traci
    except ImportError as exc:
        raise RuntimeError(
            "TraCI import failed. Activate the project virtual environment and run "
            '`python -c "import traci; print(traci.__file__)"`.'
        ) from exc
    return traci



def _read_vehicle_state(
    traci: Any,
    vehicle_id: str,
    simulation_time_ms: int,
) -> VehicleState:
    x_m, y_m = traci.vehicle.getPosition(vehicle_id)
    return VehicleState(
        vehicle_id=vehicle_id,
        simulation_time_ms=simulation_time_ms,
        x_m=float(x_m),
        y_m=float(y_m),
        lane_position_m=float(traci.vehicle.getLanePosition(vehicle_id)),
        speed_mps=float(traci.vehicle.getSpeed(vehicle_id)),
        acceleration_mps2=float(traci.vehicle.getAcceleration(vehicle_id)),
        lane_id=str(traci.vehicle.getLaneID(vehicle_id)),
        road_id=str(traci.vehicle.getRoadID(vehicle_id)),
        route_edges=tuple(
            str(edge) for edge in traci.vehicle.getRoute(vehicle_id)
        ),
        route_index=int(traci.vehicle.getRouteIndex(vehicle_id)),
    )


def collect_vehicle_snapshot(
    *,
    sumo_config: Path,
    gui: bool,
    steps: int,
    print_state: bool,
) -> tuple[VehicleState, dict[str, VehicleState], list[str]]:
    if not sumo_config.is_file():
        raise FileNotFoundError(
            f"SUMO config not found: {sumo_config}\n"
            "Generate/build the SUMO scenario first."
        )

    binary_name = "sumo-gui" if gui else "sumo"
    binary = shutil.which(binary_name)
    if binary is None:
        raise FileNotFoundError(
            f"{binary_name} was not found in PATH. "
            "Add the SUMO bin directory to PATH."
        )

    traci = _load_traci()
    command = [
        binary,
        "-c",
        str(sumo_config.resolve()),
        "--start",
        "--quit-on-end",
        "--no-step-log",
        "true",
    ]

    traci.start(command)
    last_snapshot: dict[str, VehicleState] = {}
    observed: set[str] = set()

    try:
        for step_index in range(steps):
            traci.simulationStep()
            simulation_time_ms = int(
                round(traci.simulation.getTime() * 1000)
            )
            vehicle_ids = list(traci.vehicle.getIDList())
            observed.update(vehicle_ids)

            snapshot = {
                vehicle_id: _read_vehicle_state(
                    traci,
                    vehicle_id,
                    simulation_time_ms,
                )
                for vehicle_id in vehicle_ids
            }
            if snapshot:
                last_snapshot = snapshot

            if print_state and SUBJECT_ID in snapshot:
                state = snapshot[SUBJECT_ID]
                print(
                    f"[step={step_index:03d} t={simulation_time_ms:05d} ms] "
                    f"{state.vehicle_id}: pos={state.lane_position_m:.2f} m, "
                    f"speed={state.speed_mps:.2f} m/s, "
                    f"accel={state.acceleration_mps2:.2f} m/s^2, "
                    f"lane={state.lane_id}, road={state.road_id}, "
                    f"route_index={state.route_index}, "
                    f"active_vehicles={len(snapshot)}"
                )
    finally:
        traci.close()

    if SUBJECT_ID not in last_snapshot:
        raise RuntimeError(
            f"{SUBJECT_ID} was not active during the final snapshot. "
            f"Observed IDs: {sorted(observed)}"
        )
    return (
        last_snapshot[SUBJECT_ID],
        last_snapshot,
        sorted(observed),
    )


def collect_subject_state(
    *,
    sumo_config: Path,
    gui: bool,
    steps: int,
    print_state: bool,
) -> tuple[VehicleState, list[str]]:
    """Backward-compatible wrapper used by existing tests and callers."""

    subject, _, observed = collect_vehicle_snapshot(
        sumo_config=sumo_config,
        gui=gui,
        steps=steps,
        print_state=print_state,
    )
    return subject, observed


def euclidean_distance_m(
    source: VehicleState,
    target: VehicleState,
) -> float:
    return math.hypot(source.x_m - target.x_m, source.y_m - target.y_m)


def connectivity_link(
    source_id: str,
    target_id: str,
    vehicle_states: dict[str, VehicleState],
    communication_range_m: float | None,
) -> tuple[bool, float | None]:
    source = vehicle_states.get(source_id)
    target = vehicle_states.get(target_id)

    if source is None or target is None:
        return (communication_range_m is None, None)

    distance_m = euclidean_distance_m(source, target)
    if communication_range_m is None:
        return True, distance_m
    return distance_m <= communication_range_m, distance_m


def state_to_envelopes(
    state: VehicleState,
    *,
    slot_count: int,
    slot_ms: int,
    behavior_code: str = "LANE_KEEP",
    lane_id: str | None = None,
    position_tolerance_mm: int = 1_000,
    speed_tolerance_mmps: int = 1_000,
    acceleration_tolerance_mmps2: int = 500,
) -> list[TrajectoryEnvelope]:
    """Convert one SUMO state into a deterministic short-horizon envelope plan."""

    selected_lane = lane_id or state.lane_id
    start_ms = state.simulation_time_ms
    speed_mmps = int(round(state.speed_mps * 1000))
    acceleration_mmps2 = int(round(state.acceleration_mps2 * 1000))
    position_mm = int(round(state.lane_position_m * 1000))

    envelopes: list[TrajectoryEnvelope] = []
    for index in range(slot_count):
        t0_s = (index * slot_ms) / 1000.0
        t1_s = ((index + 1) * slot_ms) / 1000.0

        predicted_start_mm = int(
            round(
                position_mm
                + speed_mmps * t0_s
                + 0.5 * acceleration_mmps2 * (t0_s**2)
            )
        )
        predicted_end_mm = int(
            round(
                position_mm
                + speed_mmps * t1_s
                + 0.5 * acceleration_mmps2 * (t1_s**2)
            )
        )
        low_position = min(predicted_start_mm, predicted_end_mm) - position_tolerance_mm
        high_position = max(predicted_start_mm, predicted_end_mm) + position_tolerance_mm

        future_speed_mmps = int(
            round(speed_mmps + acceleration_mmps2 * t1_s)
        )

        envelopes.append(
            TrajectoryEnvelope(
                segment_index=index,
                t_start_ms=start_ms + index * slot_ms,
                t_end_ms=start_ms + (index + 1) * slot_ms,
                road_id=state.road_id,
                lane_id=selected_lane,
                pos_min_mm=low_position,
                pos_max_mm=high_position,
                v_min_mmps=max(0, future_speed_mmps - speed_tolerance_mmps),
                v_max_mmps=max(0, future_speed_mmps + speed_tolerance_mmps),
                a_min_mmps2=acceleration_mmps2 - acceleration_tolerance_mmps2,
                a_max_mmps2=acceleration_mmps2 + acceleration_tolerance_mmps2,
                behavior_code=behavior_code,
            )
        )
    return envelopes


def create_attack_plans(
    state: VehicleState,
    *,
    slot_count: int,
    slot_ms: int,
) -> tuple[list[TrajectoryEnvelope], list[TrajectoryEnvelope]]:
    base = state_to_envelopes(
        state,
        slot_count=slot_count,
        slot_ms=slot_ms,
    )
    if state.lane_id.endswith("_0"):
        alternative_lane = state.lane_id[:-1] + "1"
    else:
        alternative_lane = state.lane_id[:-1] + "0" if "_" in state.lane_id else f"{state.lane_id}-ALT"

    left_plan = [
        replace(
            envelope,
            lane_id=alternative_lane,
            behavior_code="LANE_CHANGE_LEFT",
            pos_min_mm=envelope.pos_min_mm + 500,
            pos_max_mm=envelope.pos_max_mm + 500,
        )
        for envelope in base
    ]
    right_plan = [
        replace(
            envelope,
            lane_id=state.lane_id,
            behavior_code="LANE_CHANGE_RIGHT",
            pos_min_mm=envelope.pos_min_mm + 1_500,
            pos_max_mm=envelope.pos_max_mm + 1_500,
        )
        for envelope in base
    ]
    return left_plan, right_plan


def create_signer_bundle(
    algorithm: str,
    *,
    witness_count: int,
    haetae_dll: Path,
    aimer_dll: Path,
) -> SignerBundle:
    if algorithm == "mock":
        signer = MockHMACSigner()
        witness_keys = [
            (MOCK_WITNESS_KEYS[index], MOCK_WITNESS_KEYS[index])
            for index in range(1, witness_count + 1)
        ]
        return SignerBundle(
            signer=signer,
            subject_public_key=MOCK_SUBJECT_KEY,
            subject_private_key=MOCK_SUBJECT_KEY,
            witness_keys=witness_keys,
        )

    if algorithm == "haetae":
        from src.wtc.crypto_kpqc import HAETAESigner

        signer = Base64SignerAdapter(HAETAESigner(str(haetae_dll)))
    elif algorithm == "aimer":
        from src.wtc.crypto_aimer import AIMer128fSigner

        signer = Base64SignerAdapter(AIMer128fSigner(aimer_dll))
    else:
        raise ValueError(f"unsupported algorithm: {algorithm}")

    subject_public, subject_private = signer.keygen()
    witness_keys = [signer.keygen() for _ in range(witness_count)]
    return SignerBundle(
        signer=signer,
        subject_public_key=subject_public,
        subject_private_key=subject_private,
        witness_keys=witness_keys,
    )


def build_witnesses(
    signer_bundle: SignerBundle,
    *,
    witness_count: int,
    clock: MutableClock,
    logical_vehicle_count: int,
) -> list[WitnessNode]:
    witness_public_keys = {
        f"Witness-W{index + 1}": signer_bundle.witness_keys[index][0]
        for index in range(witness_count)
    }

    subject_public_keys = {SUBJECT_ID: signer_bundle.subject_public_key}
    for index in range(1, max(1, logical_vehicle_count)):
        subject_public_keys[f"Background-{index:04d}"] = signer_bundle.subject_public_key

    witnesses: list[WitnessNode] = []
    for index in range(witness_count):
        witness_id = f"Witness-W{index + 1}"
        public_key, private_key = signer_bundle.witness_keys[index]
        peer_registry = {
            key: value
            for key, value in witness_public_keys.items()
            if key != witness_id
        }
        witnesses.append(
            WitnessNode(
                witness_id=witness_id,
                subject_signer=signer_bundle.signer,
                witness_signer=signer_bundle.signer,
                subject_public_keys=subject_public_keys,
                witness_private_key=private_key,
                witness_public_keys=peer_registry,
                now_ms=clock.now_ms,
            )
        )
    return witnesses


def _direct_delivery(
    *,
    witness: WitnessNode,
    commitment: Commitment,
    sender_time_ms: int,
    clock: MutableClock,
    rng: random.Random,
    delay_ms: int,
    jitter_ms: int,
    loss_rate: float,
    in_range: bool = True,
    distance_m: float | None = None,
) -> DirectDelivery:
    if not in_range:
        return DirectDelivery(
            receiver_id=witness.witness_id,
            sent_at_ms=sender_time_ms,
            delivered_at_ms=None,
            dropped=True,
            result=None,
            in_range=False,
            distance_m=distance_m,
            drop_reason="OUT_OF_RANGE",
        )

    if rng.random() < loss_rate:
        return DirectDelivery(
            receiver_id=witness.witness_id,
            sent_at_ms=sender_time_ms,
            delivered_at_ms=None,
            dropped=True,
            result=None,
            in_range=True,
            distance_m=distance_m,
            drop_reason="NETWORK_LOSS",
        )

    jitter = int(rng.uniform(0, jitter_ms)) if jitter_ms > 0 else 0
    delivered_at_ms = sender_time_ms + delay_ms + jitter
    clock.set(delivered_at_ms)
    processing_started_ns = time.perf_counter_ns()
    result = witness.process(commitment)
    processing_wall_ms = (time.perf_counter_ns() - processing_started_ns) / 1_000_000
    return DirectDelivery(
        receiver_id=witness.witness_id,
        sent_at_ms=sender_time_ms,
        delivered_at_ms=delivered_at_ms,
        dropped=False,
        result=result,
        processing_wall_ms=processing_wall_ms,
        in_range=True,
        distance_m=distance_m,
        drop_reason=None,
    )


def _existing_observation(
    witness: WitnessNode,
    commitment: Commitment,
) -> tuple[Commitment, WitnessReceipt] | None:
    root_map = witness.observation_cache.get(commitment.consistency_key, {})
    for existing_root, receipts in root_map.items():
        if existing_root == commitment.merkle_root or not receipts:
            continue
        receipt = receipts[0]
        existing = witness.commits_by_digest.get(receipt.commitment_digest)
        if existing is not None:
            return existing, receipt
    return None


def process_gossip_compat(
    witness: WitnessNode,
    commitment: Commitment,
    receipt: WitnessReceipt,
    clock: MutableClock,
) -> ProcessResult:
    """
    Support both the older process_gossip implementation and the patched one.

    The patched WitnessNode returns CONFLICT itself. The older implementation
    accepted verified Gossip without comparing an already observed different Root.
    This wrapper performs that missing comparison only after cryptographic Gossip
    verification succeeds.
    """

    existing = _existing_observation(witness, commitment)
    previous_head = witness.active_head_cache.get(commitment.session_key)

    result = witness.process_gossip(commitment, receipt, None)
    if result.code is ResultCode.CONFLICT:
        return result
    if existing is None:
        return result
    if result.code not in (ResultCode.ACCEPT, ResultCode.DUPLICATE):
        return result

    existing_commitment, existing_receipt = existing
    local_receipt = result.receipt or receipt

    if previous_head is not None:
        witness.active_head_cache[commitment.session_key] = previous_head

    evidence = EvidenceBundle(
        commitment_a=existing_commitment,
        commitment_b=commitment,
        witness_id=witness.witness_id,
        detected_at_ms=clock.now_ms(),
        receipt_a=existing_receipt,
        receipt_b=local_receipt,
    )
    witness.evidence_store.append(evidence)
    return ProcessResult(
        code=ResultCode.CONFLICT,
        reason="verified Gossip revealed a different Root for the same consistency key",
        receipt=local_receipt,
        evidence=evidence,
    )


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


def _serialize_envelopes(envelopes: list[TrajectoryEnvelope]) -> list[dict[str, Any]]:
    return [asdict(envelope) for envelope in envelopes]


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _result_code(delivery: DirectDelivery) -> str | None:
    if delivery.result is None:
        return None
    return delivery.result.code.value


def run_background_load(
    *,
    count: int,
    factory: CommitmentFactory,
    signer_bundle: SignerBundle,
    witness: WitnessNode,
    envelopes: list[TrajectoryEnvelope],
    valid_from_ms: int,
    valid_until_ms: int,
    clock: MutableClock,
) -> dict[str, Any]:
    if count <= 0:
        return {
            "background_commitments": 0,
            "accepted": 0,
            "elapsed_ms": 0.0,
            "throughput_commitments_per_sec": None,
            "peak_memory_kib": 0.0,
        }

    tracemalloc.start()
    started = time.perf_counter_ns()
    accepted = 0

    for index in range(1, count + 1):
        subject_id = f"Background-{index:04d}"
        commitment = factory.create(
            subject_id=subject_id,
            session_id=f"LOAD-{index:04d}",
            epoch=1,
            sequence=0,
            valid_from_ms=valid_from_ms,
            valid_until_ms=valid_until_ms,
            envelopes=envelopes,
            private_key=signer_bundle.subject_private_key,
        )
        result = witness.process(commitment)
        if result.code is ResultCode.ACCEPT:
            accepted += 1

    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    throughput = None
    if elapsed_ms > 0:
        throughput = count / (elapsed_ms / 1000)

    return {
        "background_commitments": count,
        "accepted": accepted,
        "elapsed_ms": elapsed_ms,
        "throughput_commitments_per_sec": throughput,
        "peak_memory_kib": peak / 1024,
    }


async def exchange_gossip(
    *,
    witnesses: list[WitnessNode],
    accepted_updates: list[tuple[WitnessNode, Commitment, WitnessReceipt]],
    clock: MutableClock,
    start_time_ms: int,
    vehicle_states: dict[str, VehicleState],
    args: argparse.Namespace,
) -> tuple[
    GossipNetworkEmulator,
    list[DetectionRecord],
    list[dict[str, Any]],
]:
    emulator = GossipNetworkEmulator(
        base_delay_ms=args.delay_ms,
        jitter_ms=args.jitter_ms,
        loss_rate=args.loss_rate,
        duplicate_rate=args.duplicate_rate,
        reorder_rate=args.reorder_rate,
        seed=args.seed + 10_000,
    )
    emulator.current_time_ms = start_time_ms
    detections: list[DetectionRecord] = []
    out_of_range_links: list[dict[str, Any]] = []

    for witness in witnesses:
        async def handler(
            commitment_in: Commitment,
            receipt_in: WitnessReceipt,
            target: WitnessNode = witness,
        ) -> ResultCode:
            clock.set(emulator.current_time_ms)
            processing_started_ns = time.perf_counter_ns()
            result = process_gossip_compat(
                target,
                commitment_in,
                receipt_in,
                clock,
            )
            detected_wall_ns = time.perf_counter_ns()
            logic_wall_ms = (detected_wall_ns - processing_started_ns) / 1_000_000
            if result.code is ResultCode.CONFLICT:
                detections.append(
                    DetectionRecord(
                        witness_id=target.witness_id,
                        detected_at_ms=clock.now_ms(),
                        result=result,
                        logic_wall_ms=logic_wall_ms,
                        detected_wall_ns=detected_wall_ns,
                    )
                )
            return result.code

        emulator.register_handler(witness.witness_id, handler)

    gossip_send_time = start_time_ms + args.gossip_ms
    for source_witness, commitment, receipt in accepted_updates:
        for target_witness in witnesses:
            if target_witness.witness_id == source_witness.witness_id:
                continue

            in_range, distance_m = connectivity_link(
                source_witness.witness_id,
                target_witness.witness_id,
                vehicle_states,
                args.communication_range_m,
            )
            if not in_range:
                out_of_range_links.append(
                    {
                        "source_id": source_witness.witness_id,
                        "target_id": target_witness.witness_id,
                        "distance_m": distance_m,
                        "communication_range_m": args.communication_range_m,
                        "commitment_root": commitment.merkle_root,
                    }
                )
                continue

            emulator.send_gossip(
                source_witness.witness_id,
                target_witness.witness_id,
                commitment,
                receipt,
                send_time_ms=gossip_send_time,
            )

    await emulator.run_until_empty()
    return emulator, detections, out_of_range_links


def run_protocol(
    *,
    state: VehicleState,
    vehicle_states: dict[str, VehicleState],
    observed_vehicle_ids: list[str],
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[EvidenceBundle]]:
    run_started = time.perf_counter_ns()
    rng = random.Random(args.seed)
    clock = MutableClock(state.simulation_time_ms)

    signer_started = time.perf_counter_ns()
    signer_bundle = create_signer_bundle(
        args.algorithm,
        witness_count=args.witness_count,
        haetae_dll=args.haetae_dll,
        aimer_dll=args.aimer_dll,
    )
    signer_setup_ms = (time.perf_counter_ns() - signer_started) / 1_000_000

    factory = CommitmentFactory(signer_bundle.signer)
    witnesses = build_witnesses(
        signer_bundle,
        witness_count=args.witness_count,
        clock=clock,
        logical_vehicle_count=args.vehicle_count,
    )

    base_envelopes = state_to_envelopes(
        state,
        slot_count=args.slots,
        slot_ms=args.slot_ms,
    )
    valid_from_ms = state.simulation_time_ms
    valid_until_ms = valid_from_ms + max(60_000, args.slots * args.slot_ms + 10_000)

    initial = factory.create(
        subject_id=SUBJECT_ID,
        session_id=SESSION_ID,
        epoch=1,
        sequence=0,
        valid_from_ms=valid_from_ms,
        valid_until_ms=valid_until_ms,
        envelopes=base_envelopes,
        private_key=signer_bundle.subject_private_key,
    )

    subject_witness_links = {
        witness.witness_id: connectivity_link(
            SUBJECT_ID,
            witness.witness_id,
            vehicle_states,
            args.communication_range_m,
        )
        for witness in witnesses
    }

    initial_deliveries = []
    for witness in witnesses:
        in_range, distance_m = subject_witness_links[witness.witness_id]
        initial_deliveries.append(
            _direct_delivery(
                witness=witness,
                commitment=initial,
                sender_time_ms=state.simulation_time_ms,
                clock=clock,
                rng=rng,
                delay_ms=args.delay_ms,
                jitter_ms=args.jitter_ms,
                loss_rate=args.loss_rate,
                in_range=in_range,
                distance_m=distance_m,
            )
        )

    logical_background_count = (
        0
        if args.require_physical_vehicles
        else max(0, args.vehicle_count - len(vehicle_states))
    )
    background_metrics = run_background_load(
        count=logical_background_count,
        factory=factory,
        signer_bundle=signer_bundle,
        witness=witnesses[0],
        envelopes=base_envelopes,
        valid_from_ms=valid_from_ms,
        valid_until_ms=valid_until_ms,
        clock=clock,
    )

    if args.scenario == "normal":
        accepted = sum(
            1
            for delivery in initial_deliveries
            if delivery.result is not None
            and delivery.result.code in (ResultCode.ACCEPT, ResultCode.DUPLICATE)
        )
        payload = {
            "scenario": "normal",
            "normal_accept_count": accepted,
            "initial_delivery_codes": [_result_code(item) for item in initial_deliveries],
            "conflict_detected": False,
            "evidence_generated": False,
            "observable_attack": None,
            "detection_e2e_ms": None,
            "detection_e2e_simulated_ms": None,
            "detection_logic_ms": None,
            "detection_logic_wall_ms": None,
            "attack_to_evidence_wall_ms": None,
            "gossip_events": {},
            "background_load": background_metrics,
            "communication_range_m": args.communication_range_m,
            "subject_witness_distances_m": {
                witness_id: distance_m
                for witness_id, (_, distance_m)
                in subject_witness_links.items()
            },
            "subject_reachable_witnesses": [
                witness_id
                for witness_id, (in_range, _)
                in subject_witness_links.items()
                if in_range
            ],
            "out_of_range_direct_count": sum(
                1 for delivery in initial_deliveries if not delivery.in_range
            ),
            "out_of_range_gossip_count": 0,
        }
        total_wall_ms = (time.perf_counter_ns() - run_started) / 1_000_000
        payload["total_wall_ms"] = total_wall_ms
        payload["signer_setup_ms"] = signer_setup_ms
        return payload, []

    left_plan, right_plan = create_attack_plans(
        state,
        slot_count=args.slots,
        slot_ms=args.slot_ms,
    )
    update_a = factory.create(
        subject_id=SUBJECT_ID,
        session_id=SESSION_ID,
        epoch=1,
        sequence=1,
        valid_from_ms=valid_from_ms,
        valid_until_ms=valid_until_ms,
        envelopes=left_plan,
        parent_root=initial.merkle_root,
        update_reason="ATTACK_BRANCH_A",
        private_key=signer_bundle.subject_private_key,
    )
    update_b = factory.create(
        subject_id=SUBJECT_ID,
        session_id=SESSION_ID,
        epoch=1,
        sequence=1,
        valid_from_ms=valid_from_ms,
        valid_until_ms=valid_until_ms,
        envelopes=right_plan,
        parent_root=initial.merkle_root,
        update_reason="ATTACK_BRANCH_B",
        private_key=signer_bundle.subject_private_key,
    )

    attack_send_time = max(
        state.simulation_time_ms + 1,
        max(
            (
                delivery.delivered_at_ms
                for delivery in initial_deliveries
                if delivery.delivered_at_ms is not None
            ),
            default=state.simulation_time_ms,
        )
        + 1,
    )

    accepted_updates: list[tuple[WitnessNode, Commitment, WitnessReceipt]] = []
    attack_deliveries: list[DirectDelivery] = []
    group_a_receivers: list[str] = []
    group_b_receivers: list[str] = []

    if args.witness_count == 1:
        target_pairs = [
            (witnesses[0], update_a, "A"),
            (witnesses[0], update_b, "B"),
        ]
    else:
        split = max(1, args.witness_count // 2)
        target_pairs = []
        for index, witness in enumerate(witnesses):
            branch = "A" if index < split else "B"
            target_pairs.append(
                (witness, update_a if branch == "A" else update_b, branch)
            )

    attack_wall_started_ns = time.perf_counter_ns()

    for witness, commitment, branch in target_pairs:
        in_range, distance_m = subject_witness_links[witness.witness_id]
        delivery = _direct_delivery(
            witness=witness,
            commitment=commitment,
            sender_time_ms=attack_send_time,
            clock=clock,
            rng=rng,
            delay_ms=args.delay_ms,
            jitter_ms=args.jitter_ms,
            loss_rate=args.loss_rate,
            in_range=in_range,
            distance_m=distance_m,
        )
        attack_deliveries.append(delivery)
        if branch == "A":
            group_a_receivers.append(witness.witness_id)
        else:
            group_b_receivers.append(witness.witness_id)

        if (
            delivery.result is not None
            and delivery.result.receipt is not None
            and delivery.result.code
            in (ResultCode.ACCEPT, ResultCode.VALID_UPDATE, ResultCode.CONFLICT)
        ):
            accepted_updates.append(
                (witness, commitment, delivery.result.receipt)
            )

    observable_a = any(
        commitment.merkle_root == update_a.merkle_root
        for _, commitment, _ in accepted_updates
    )
    observable_b = any(
        commitment.merkle_root == update_b.merkle_root
        for _, commitment, _ in accepted_updates
    )
    observable_attack = observable_a and observable_b

    direct_conflict_deliveries = [
        delivery
        for delivery in attack_deliveries
        if delivery.result is not None
        and delivery.result.code is ResultCode.CONFLICT
    ]

    gossip_start_time = max(
        (
            delivery.delivered_at_ms
            for delivery in attack_deliveries
            if delivery.delivered_at_ms is not None
        ),
        default=attack_send_time,
    )

    emulator, gossip_detections, out_of_range_gossip_links = asyncio.run(
        exchange_gossip(
            witnesses=witnesses,
            accepted_updates=accepted_updates,
            clock=clock,
            start_time_ms=gossip_start_time,
            vehicle_states=vehicle_states,
            args=args,
        )
    )

    evidence: list[EvidenceBundle] = []
    for delivery in direct_conflict_deliveries:
        if delivery.result is not None and delivery.result.evidence is not None:
            evidence.append(delivery.result.evidence)
    for detection in gossip_detections:
        if detection.result.evidence is not None:
            evidence.append(detection.result.evidence)

    # Remove exact duplicate Evidence objects caused by duplicate Gossip delivery.
    unique_evidence: list[EvidenceBundle] = []
    seen_evidence: set[tuple[str, str, str]] = set()
    for item in evidence:
        key = (
            item.witness_id,
            item.commitment_a.merkle_root,
            item.commitment_b.merkle_root,
        )
        if key not in seen_evidence:
            seen_evidence.add(key)
            unique_evidence.append(item)

    detection_times = [item.detected_at_ms for item in unique_evidence]
    first_detection_ms = min(detection_times) if detection_times else None
    first_gossip_delivery = min(
        (
            event.timestamp_ms
            for event in emulator.events
            if event.event_type == "delivered"
        ),
        default=None,
    )

    simulated_e2e_ms = (
        None
        if first_detection_ms is None
        else first_detection_ms - attack_send_time
    )

    logic_wall_values = [detection.logic_wall_ms for detection in gossip_detections]
    logic_wall_values.extend(
        delivery.processing_wall_ms
        for delivery in direct_conflict_deliveries
        if delivery.processing_wall_ms is not None
    )
    first_logic_wall_ms = min(logic_wall_values) if logic_wall_values else None

    detection_wall_candidates = [
        detection.detected_wall_ns
        for detection in gossip_detections
    ]
    if direct_conflict_deliveries:
        # Direct conflict timing ends when the corresponding process call returns.
        # Use the current wall time as a conservative upper bound.
        detection_wall_candidates.append(time.perf_counter_ns())
    first_detection_wall_ns = (
        min(detection_wall_candidates)
        if detection_wall_candidates
        else None
    )
    attack_to_evidence_wall_ms = (
        None
        if first_detection_wall_ns is None
        else (first_detection_wall_ns - attack_wall_started_ns) / 1_000_000
    )

    event_counts: dict[str, int] = {}
    for event in emulator.events:
        event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1

    total_wall_ms = (time.perf_counter_ns() - run_started) / 1_000_000
    payload = {
        "scenario": "equivocation",
        "signer_setup_ms": signer_setup_ms,
        "total_wall_ms": total_wall_ms,
        "initial_root": initial.merkle_root,
        "attack_root_a": update_a.merkle_root,
        "attack_root_b": update_b.merkle_root,
        "roots_are_different": update_a.merkle_root != update_b.merkle_root,
        "group_a_receivers": group_a_receivers,
        "group_b_receivers": group_b_receivers,
        "initial_delivery_codes": [_result_code(item) for item in initial_deliveries],
        "attack_delivery_codes": [_result_code(item) for item in attack_deliveries],
        "accepted_update_count": len(accepted_updates),
        "observable_attack": observable_attack,
        "conflict_detected": bool(unique_evidence),
        "evidence_generated": bool(unique_evidence),
        "evidence_count": len(unique_evidence),
        # Backward-compatible alias. This is simulated logical time, not wall time.
        "detection_e2e_ms": simulated_e2e_ms,
        "detection_e2e_simulated_ms": simulated_e2e_ms,
        # This field now records actual processing wall time for the first conflict.
        "detection_logic_ms": first_logic_wall_ms,
        "detection_logic_wall_ms": first_logic_wall_ms,
        "detection_logic_wall_samples_ms": logic_wall_values,
        "attack_to_evidence_wall_ms": attack_to_evidence_wall_ms,
        "measurement_notes": {
            "detection_e2e_simulated_ms": (
                "logical emulator time from second attack-branch send to Evidence generation"
            ),
            "detection_logic_wall_ms": (
                "wall-clock time spent verifying Gossip, checking caches, and creating Evidence"
            ),
            "attack_to_evidence_wall_ms": (
                "wall-clock processing time from attack delivery phase start to first Evidence; "
                "simulated network delay is not slept in real time"
            ),
        },
        "gossip_events": event_counts,
        "gossip_event_log": [asdict(event) for event in emulator.events],
        "communication_range_m": args.communication_range_m,
        "subject_witness_distances_m": {
            witness_id: distance_m
            for witness_id, (_, distance_m)
            in subject_witness_links.items()
        },
        "subject_reachable_witnesses": [
            witness_id
            for witness_id, (in_range, _)
            in subject_witness_links.items()
            if in_range
        ],
        "out_of_range_direct_count": sum(
            1 for delivery in attack_deliveries if not delivery.in_range
        ),
        "out_of_range_gossip_count": len(out_of_range_gossip_links),
        "out_of_range_gossip_links": out_of_range_gossip_links,
        "background_load": background_metrics,
    }
    return payload, unique_evidence


def main() -> int:
    args = parse_args()
    validate_args(args)

    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        + f"_{args.scenario}_{args.algorithm}_seed{args.seed}"
    )
    output_json = args.output_json or ARTIFACT_ROOT / "runs" / f"{run_id}.json"
    evidence_json = (
        args.evidence_json
        or ARTIFACT_ROOT
        / "evidence"
        / f"evidence_{run_id}.json"
    )

    try:
        state, vehicle_states, observed_vehicle_ids = collect_vehicle_snapshot(
            sumo_config=args.sumo_config,
            gui=args.gui,
            steps=args.steps,
            print_state=args.print_state or args.scenario == "state",
        )

        expected_witness_ids = {
            f"Witness-W{index}"
            for index in range(1, args.witness_count + 1)
        }
        missing_witness_ids = sorted(
            expected_witness_ids - set(vehicle_states)
        )
        if args.require_physical_vehicles:
            if len(vehicle_states) < args.vehicle_count:
                raise RuntimeError(
                    "physical SUMO vehicle requirement not met: "
                    f"requested={args.vehicle_count}, active={len(vehicle_states)}"
                )
            if missing_witness_ids:
                raise RuntimeError(
                    "requested physical Witness vehicles are missing: "
                    + ", ".join(missing_witness_ids)
                )

        physical_mode = (
            len(vehicle_states) >= args.vehicle_count
            and not missing_witness_ids
        )

        base_result: dict[str, Any] = {
            "run_id": run_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "scenario": args.scenario,
            "algorithm": args.algorithm,
            "seed": args.seed,
            "sumo_config": str(args.sumo_config.resolve()),
            "state": state.to_dict(),
            "observed_sumo_vehicle_ids": observed_vehicle_ids,
            "observed_sumo_vehicle_count": len(observed_vehicle_ids),
            "active_sumo_vehicle_ids": sorted(vehicle_states),
            "physical_sumo_vehicle_count": len(vehicle_states),
            "requested_vehicle_count": args.vehicle_count,
            "physical_vehicle_requirement_met": (
                len(vehicle_states) >= args.vehicle_count
                and not missing_witness_ids
            ),
            "vehicle_count_mode": (
                "physical SUMO vehicles"
                if physical_mode
                else "physical SUMO vehicles plus logical protocol background load"
            ),
            "witness_count": args.witness_count,
            "missing_physical_witness_ids": missing_witness_ids,
            "communication_range_m": args.communication_range_m,
            "slot_count": args.slots,
            "slot_ms": args.slot_ms,
            "delay_ms": args.delay_ms,
            "jitter_ms": args.jitter_ms,
            "loss_rate": args.loss_rate,
            "duplicate_rate": args.duplicate_rate,
            "reorder_rate": args.reorder_rate,
            "gossip_period_ms": args.gossip_ms,
        }

        if args.scenario == "state":
            base_result["status"] = "PASS"
            _write_json(output_json, base_result)
            print(json.dumps(base_result, ensure_ascii=False, indent=2))
            print(f"\nResult written to: {output_json.resolve()}")
            print("SUMO/TRACI STATE COLLECTION: PASS")
            return 0

        base_envelopes = state_to_envelopes(
            state,
            slot_count=args.slots,
            slot_ms=args.slot_ms,
        )
        base_result["trajectory_envelopes"] = _serialize_envelopes(base_envelopes)

        if args.scenario == "envelope":
            base_result["status"] = "PASS"
            _write_json(output_json, base_result)
            print(json.dumps(base_result, ensure_ascii=False, indent=2))
            print(f"\nResult written to: {output_json.resolve()}")
            print("SUMO TO TRAJECTORY ENVELOPE: PASS")
            return 0

        protocol_result, evidence = run_protocol(
            state=state,
            vehicle_states=vehicle_states,
            observed_vehicle_ids=observed_vehicle_ids,
            args=args,
        )
        base_result.update(protocol_result)

        if evidence:
            evidence_payload = {
                "run_id": run_id,
                "evidence_bundles": [item.to_dict() for item in evidence],
            }
            _write_json(evidence_json, evidence_payload)
            base_result["evidence_file"] = str(evidence_json.resolve())
        else:
            base_result["evidence_file"] = None

        if args.scenario == "normal":
            passed = (
                base_result.get("normal_accept_count", 0) > 0
                and not base_result.get("conflict_detected", False)
            )
        else:
            passed = bool(base_result.get("conflict_detected", False))
            if args.allow_no_conflict:
                passed = True

        base_result["status"] = "PASS" if passed else "FAIL"
        _write_json(output_json, base_result)

        print("\n=== KpqC WTC SUMO RUN ===")
        print(f"Scenario           : {args.scenario}")
        print(f"Algorithm          : {args.algorithm}")
        print(f"SUMO vehicles seen : {len(observed_vehicle_ids)}")
        print(f"Active physical N  : {len(vehicle_states)}")
        print(f"Requested N        : {args.vehicle_count}")
        print(f"Witnesses          : {args.witness_count}")
        print(f"Radio range        : {args.communication_range_m} m")
        print(f"Delay / loss       : {args.delay_ms} ms / {args.loss_rate:.1%}")
        print(f"Conflict detected  : {base_result.get('conflict_detected')}")
        print(f"Observable attack  : {base_result.get('observable_attack')}")
        print(f"Evidence count     : {base_result.get('evidence_count', 0)}")
        print(
            f"Simulated E2E      : "
            f"{base_result.get('detection_e2e_simulated_ms')} ms"
        )
        print(
            f"Logic wall time    : "
            f"{base_result.get('detection_logic_wall_ms')} ms"
        )
        print(f"Result JSON        : {output_json.resolve()}")
        if base_result.get("evidence_file"):
            print(f"Evidence JSON      : {base_result['evidence_file']}")

        if args.scenario == "normal":
            print(
                "NORMAL WTC SUMO: "
                + ("PASS" if base_result["status"] == "PASS" else "FAIL")
            )
        else:
            print(
                "EQUIVOCATION WTC SUMO: "
                + ("PASS" if base_result["status"] == "PASS" else "FAIL")
            )
        return 0 if passed else 1

    except Exception as exc:
        error_payload = {
            "run_id": run_id,
            "status": "ERROR",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        _write_json(output_json, error_payload)
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(f"Error result written to: {output_json.resolve()}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
