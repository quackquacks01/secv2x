from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import traci


EXPECTED_VEHICLES = {"Vehicle-A", "Witness-W1", "Witness-W2"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the minimal SUMO WTC scenario.")
    parser.add_argument("--gui", action="store_true", help="Use sumo-gui instead of sumo.")
    parser.add_argument("--steps", type=int, default=100, help="Number of TraCI simulation steps.")
    parser.add_argument(
        "--print-every",
        type=int,
        default=10,
        help="Print vehicle states every N simulation steps.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    project_root = Path(__file__).resolve().parents[3]
    config_file = (
        project_root
        / "simulation"
        / "sumo"
        / "scenarios"
        / "minimal"
        / "minimal.sumocfg"
    )
    net_file = config_file.with_name("minimal.net.xml")

    if not config_file.exists():
        print(f"ERROR: SUMO config not found: {config_file}")
        return 1
    if not net_file.exists():
        print(f"ERROR: SUMO network not found: {net_file}")
        print("Run first:")
        print("  python -m simulation.sumo.controllers.build_minimal_scenario")
        return 1

    binary_name = "sumo-gui" if args.gui else "sumo"
    sumo_binary = shutil.which(binary_name)
    if sumo_binary is None:
        print(f"ERROR: {binary_name} was not found in PATH.")
        return 1

    command = [
        sumo_binary,
        "-c",
        str(config_file),
        "--start",
        "--quit-on-end",
    ]

    print(f"Starting {binary_name}: {config_file}")
    traci.start(command)

    observed: set[str] = set()
    try:
        for step in range(args.steps):
            traci.simulationStep()
            sim_time_ms = int(round(traci.simulation.getTime() * 1000))
            vehicle_ids = set(traci.vehicle.getIDList())
            observed.update(vehicle_ids)

            if step % args.print_every == 0:
                print(f"\n[simulation_time={sim_time_ms} ms]")
                for vehicle_id in sorted(vehicle_ids):
                    x, y = traci.vehicle.getPosition(vehicle_id)
                    speed = traci.vehicle.getSpeed(vehicle_id)
                    lane_id = traci.vehicle.getLaneID(vehicle_id)
                    print(
                        f"{vehicle_id}: "
                        f"position=({x:.2f}, {y:.2f}) m, "
                        f"speed={speed:.2f} m/s, "
                        f"lane={lane_id}"
                    )
    finally:
        traci.close()

    missing = EXPECTED_VEHICLES - observed
    if missing:
        print(f"ERROR: vehicles not observed: {sorted(missing)}")
        print("MINIMAL SUMO/TRACI SCENARIO: FAIL")
        return 1

    print("\nObserved vehicles:", ", ".join(sorted(observed)))
    print("MINIMAL SUMO/TRACI SCENARIO: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
