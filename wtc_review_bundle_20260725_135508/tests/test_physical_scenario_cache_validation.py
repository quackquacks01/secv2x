from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

from simulation.experiments.run_sweep import validate_physical_scenario


def write_scenario(
    root: Path,
    *,
    manifest_vehicle_count: int,
    route_vehicle_count: int,
    witness_count: int = 5,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "scalable.sumocfg").write_text(
        "<configuration/>",
        encoding="utf-8",
    )
    (root / "scalable.net.xml").write_text(
        "<net/>",
        encoding="utf-8",
    )

    routes = ET.Element("routes")
    ids = ["Vehicle-A"] + [
        f"Witness-W{index}"
        for index in range(1, witness_count + 1)
    ]
    while len(ids) < route_vehicle_count:
        ids.append(f"Vehicle-{len(ids):04d}")

    for vehicle_id in ids[:route_vehicle_count]:
        ET.SubElement(routes, "vehicle", {"id": vehicle_id})
    ET.ElementTree(routes).write(
        root / "scalable.rou.xml",
        encoding="utf-8",
        xml_declaration=True,
    )

    manifest = {
        "vehicle_count": manifest_vehicle_count,
        "witness_count": witness_count,
        "vehicles": [{"vehicle_id": f"v{index}"} for index in range(manifest_vehicle_count)],
    }
    (root / "scenario_manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


def test_rejects_stale_n10_route_in_n50_directory(tmp_path):
    write_scenario(
        tmp_path,
        manifest_vehicle_count=50,
        route_vehicle_count=10,
    )

    valid, reason = validate_physical_scenario(
        output_dir=tmp_path,
        vehicle_count=50,
        witness_count=5,
    )

    assert valid is False
    assert "route vehicle count mismatch" in reason


def test_accepts_matching_n50_scenario(tmp_path):
    write_scenario(
        tmp_path,
        manifest_vehicle_count=50,
        route_vehicle_count=50,
    )

    valid, reason = validate_physical_scenario(
        output_dir=tmp_path,
        vehicle_count=50,
        witness_count=5,
    )

    assert valid is True
