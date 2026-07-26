from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCENARIO_ROOT = (
    PROJECT_ROOT / "simulation" / "sumo" / "scenarios" / "scalable"
)


VEHICLE_LENGTH_M = 5.0
VEHICLE_MIN_GAP_M = 2.5
VEHICLE_TAU_S = 1.0
INSERTION_MARGIN_M = 5.0


def minimum_safe_background_spacing_m(speed_mps: float) -> float:
    """
    Conservative same-lane spacing for simultaneous fixed-position insertion.

    SUMO's car-following insertion check needs more than length + minGap when
    vehicles depart at non-zero speed. We include one reaction-time distance
    plus a small margin and round up to the next 5 m.
    """

    raw_spacing = (
        VEHICLE_LENGTH_M
        + VEHICLE_MIN_GAP_M
        + speed_mps * VEHICLE_TAU_S
        + INSERTION_MARGIN_M
    )
    return math.ceil(raw_spacing / 5.0) * 5.0


@dataclass(frozen=True)
class VehicleSpec:
    vehicle_id: str
    lane_index: int
    depart_position_m: float
    depart_speed_mps: float
    role: str
    color: str


def _indent(root: ET.Element) -> None:
    try:
        ET.indent(root, space="    ")
    except AttributeError:
        pass


def _write_xml(path: Path, root: ET.Element) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _indent(root)
    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def build_vehicle_specs(
    vehicle_count: int,
    witness_count: int,
    *,
    lane_count: int = 4,
    subject_position_m: float = 200.0,
    witness_spacing_m: float = 30.0,
    background_start_m: float = 500.0,
    background_spacing_m: float = 30.0,
    speed_mps: float = 13.89,
) -> list[VehicleSpec]:
    if vehicle_count < 1:
        raise ValueError("vehicle_count must be positive")
    if witness_count < 1:
        raise ValueError("witness_count must be positive")
    if vehicle_count < witness_count + 1:
        raise ValueError(
            "vehicle_count must include Vehicle-A and every Witness vehicle"
        )
    if lane_count < 1:
        raise ValueError("lane_count must be positive")
    if witness_spacing_m <= 0 or background_spacing_m <= 0:
        raise ValueError("vehicle spacing must be positive")

    safe_background_spacing_m = minimum_safe_background_spacing_m(
        speed_mps
    )
    effective_background_spacing_m = max(
        background_spacing_m,
        safe_background_spacing_m,
    )

    specs: list[VehicleSpec] = [
        VehicleSpec(
            vehicle_id="Vehicle-A",
            lane_index=0,
            depart_position_m=subject_position_m,
            depart_speed_mps=speed_mps,
            role="SUBJECT",
            color="1,0,0",
        )
    ]

    for index in range(1, witness_count + 1):
        distance_level = (index + 1) // 2
        lane_index = (index - 1) % min(2, lane_count)
        specs.append(
            VehicleSpec(
                vehicle_id=f"Witness-W{index}",
                lane_index=lane_index,
                depart_position_m=(
                    subject_position_m + distance_level * witness_spacing_m
                ),
                depart_speed_mps=speed_mps,
                role="WITNESS",
                color="0,1,0" if index % 2 else "1,1,0",
            )
        )

    background_count = vehicle_count - len(specs)
    for index in range(background_count):
        lane_index = index % lane_count
        row = index // lane_count
        specs.append(
            VehicleSpec(
                vehicle_id=f"Vehicle-{index + 1:04d}",
                lane_index=lane_index,
                depart_position_m=(
                    background_start_m + row * effective_background_spacing_m
                ),
                depart_speed_mps=speed_mps,
                role="BACKGROUND",
                color="0.2,0.4,1",
            )
        )

    return specs


def required_road_length_m(
    specs: Iterable[VehicleSpec],
    *,
    margin_m: float = 500.0,
    minimum_m: float = 2_000.0,
) -> float:
    max_position = max(spec.depart_position_m for spec in specs)
    return max(minimum_m, max_position + margin_m)


def write_network_sources(
    output_dir: Path,
    *,
    road_length_m: float,
    lane_count: int,
    speed_mps: float,
) -> tuple[Path, Path]:
    nodes_path = output_dir / "scalable.nod.xml"
    edges_path = output_dir / "scalable.edg.xml"

    nodes = ET.Element("nodes")
    ET.SubElement(
        nodes,
        "node",
        {
            "id": "N0",
            "x": "0.0",
            "y": "0.0",
            "type": "priority",
        },
    )
    ET.SubElement(
        nodes,
        "node",
        {
            "id": "N1",
            "x": f"{road_length_m:.2f}",
            "y": "0.0",
            "type": "priority",
        },
    )
    _write_xml(nodes_path, nodes)

    edges = ET.Element("edges")
    ET.SubElement(
        edges,
        "edge",
        {
            "id": "E0",
            "from": "N0",
            "to": "N1",
            "numLanes": str(lane_count),
            "speed": f"{speed_mps:.2f}",
        },
    )
    _write_xml(edges_path, edges)
    return nodes_path, edges_path


def write_routes(
    output_dir: Path,
    specs: list[VehicleSpec],
    *,
    speed_mps: float,
) -> Path:
    route_path = output_dir / "scalable.rou.xml"
    routes = ET.Element("routes")

    ET.SubElement(
        routes,
        "vType",
        {
            "id": "wtcCar",
            "accel": "2.6",
            "decel": "4.5",
            "sigma": "0",
            "length": "5.0",
            "minGap": "2.5",
            "maxSpeed": f"{speed_mps:.2f}",
        },
    )
    ET.SubElement(routes, "route", {"id": "straightRoute", "edges": "E0"})

    for spec in specs:
        ET.SubElement(
            routes,
            "vehicle",
            {
                "id": spec.vehicle_id,
                "type": "wtcCar",
                "route": "straightRoute",
                "depart": "0.0",
                "departLane": str(spec.lane_index),
                "departPos": f"{spec.depart_position_m:.2f}",
                "departSpeed": f"{spec.depart_speed_mps:.2f}",
                "color": spec.color,
            },
        )

    _write_xml(route_path, routes)
    return route_path


def write_config(
    output_dir: Path,
    *,
    end_time_s: float = 120.0,
    step_length_s: float = 0.1,
) -> Path:
    config_path = output_dir / "scalable.sumocfg"
    configuration = ET.Element("configuration")

    input_node = ET.SubElement(configuration, "input")
    ET.SubElement(input_node, "net-file", {"value": "scalable.net.xml"})
    ET.SubElement(input_node, "route-files", {"value": "scalable.rou.xml"})

    time_node = ET.SubElement(configuration, "time")
    ET.SubElement(time_node, "begin", {"value": "0"})
    ET.SubElement(time_node, "end", {"value": f"{end_time_s:g}"})
    ET.SubElement(
        time_node,
        "step-length",
        {"value": f"{step_length_s:g}"},
    )

    report_node = ET.SubElement(configuration, "report")
    ET.SubElement(report_node, "no-step-log", {"value": "true"})
    ET.SubElement(report_node, "verbose", {"value": "false"})

    _write_xml(config_path, configuration)
    return config_path


def run_netconvert(
    nodes_path: Path,
    edges_path: Path,
    network_path: Path,
) -> None:
    executable = shutil.which("netconvert")
    if executable is None:
        raise FileNotFoundError(
            "netconvert was not found in PATH. Add the SUMO bin directory."
        )

    command = [
        executable,
        "--node-files",
        str(nodes_path),
        "--edge-files",
        str(edges_path),
        "--output-file",
        str(network_path),
        "--no-turnarounds",
        "true",
    ]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0 or not network_path.is_file():
        raise RuntimeError(
            f"netconvert failed with exit code {completed.returncode}"
        )


def generate_scenario(
    *,
    vehicle_count: int,
    witness_count: int,
    output_dir: Path | None = None,
    lane_count: int = 4,
    witness_spacing_m: float = 30.0,
    background_spacing_m: float = 30.0,
    speed_mps: float = 13.89,
    skip_netconvert: bool = False,
) -> Path:
    if output_dir is None:
        output_dir = (
            DEFAULT_SCENARIO_ROOT
            / f"N{vehicle_count}_W{witness_count}"
        )
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    specs = build_vehicle_specs(
        vehicle_count,
        witness_count,
        lane_count=lane_count,
        witness_spacing_m=witness_spacing_m,
        background_spacing_m=background_spacing_m,
        speed_mps=speed_mps,
    )
    road_length_m = required_road_length_m(specs)

    nodes_path, edges_path = write_network_sources(
        output_dir,
        road_length_m=road_length_m,
        lane_count=lane_count,
        speed_mps=speed_mps,
    )
    route_path = write_routes(
        output_dir,
        specs,
        speed_mps=speed_mps,
    )
    config_path = write_config(output_dir)
    network_path = output_dir / "scalable.net.xml"

    if not skip_netconvert:
        run_netconvert(nodes_path, edges_path, network_path)

    manifest = {
        "vehicle_count": vehicle_count,
        "witness_count": witness_count,
        "lane_count": lane_count,
        "road_length_m": road_length_m,
        "witness_spacing_m": witness_spacing_m,
        "background_spacing_m_requested": background_spacing_m,
        "background_spacing_m": max(
            background_spacing_m,
            minimum_safe_background_spacing_m(speed_mps),
        ),
        "minimum_safe_background_spacing_m": (
            minimum_safe_background_spacing_m(speed_mps)
        ),
        "speed_mps": speed_mps,
        "network_built": network_path.is_file(),
        "config_file": str(config_path),
        "network_file": str(network_path),
        "route_file": str(route_path),
        "vehicles": [asdict(spec) for spec in specs],
        "interpretation": (
            "All listed vehicles are explicit physical SUMO vehicles. "
            "Only Vehicle-A is the attacking Subject; Witness-W* vehicles "
            "participate in WTC observation and Gossip."
        ),
    }
    (output_dir / "scenario_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return config_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a scalable physical SUMO WTC scenario."
    )
    parser.add_argument("--vehicle-count", type=int, required=True)
    parser.add_argument("--witness-count", type=int, default=5)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--lane-count", type=int, default=4)
    parser.add_argument("--witness-spacing-m", type=float, default=30.0)
    parser.add_argument("--background-spacing-m", type=float, default=30.0)
    parser.add_argument("--speed-mps", type=float, default=13.89)
    parser.add_argument("--skip-netconvert", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config_path = generate_scenario(
            vehicle_count=args.vehicle_count,
            witness_count=args.witness_count,
            output_dir=args.output_dir,
            lane_count=args.lane_count,
            witness_spacing_m=args.witness_spacing_m,
            background_spacing_m=args.background_spacing_m,
            speed_mps=args.speed_mps,
            skip_netconvert=args.skip_netconvert,
        )
    except Exception as exc:
        print(f"SCALABLE SUMO SCENARIO: FAIL ({type(exc).__name__}: {exc})")
        return 1

    print(f"Config: {config_path}")
    print("SCALABLE SUMO SCENARIO: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
