from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET

from simulation.sumo.generators.generate_scalable_scenario import (
    build_vehicle_specs,
    generate_scenario,
    required_road_length_m,
)


def test_build_vehicle_specs_contains_physical_subject_and_witnesses():
    specs = build_vehicle_specs(
        vehicle_count=10,
        witness_count=5,
        lane_count=4,
    )

    assert len(specs) == 10
    assert specs[0].vehicle_id == "Vehicle-A"
    assert {spec.vehicle_id for spec in specs[1:6]} == {
        "Witness-W1",
        "Witness-W2",
        "Witness-W3",
        "Witness-W4",
        "Witness-W5",
    }
    assert len({spec.vehicle_id for spec in specs}) == 10


def test_witness_layout_supports_range_based_observability():
    specs = {
        spec.vehicle_id: spec
        for spec in build_vehicle_specs(
            vehicle_count=10,
            witness_count=5,
            lane_count=4,
        )
    }
    subject = specs["Vehicle-A"]

    distance_w1 = abs(
        specs["Witness-W1"].depart_position_m
        - subject.depart_position_m
    )
    distance_w5 = abs(
        specs["Witness-W5"].depart_position_m
        - subject.depart_position_m
    )

    assert distance_w1 == 30.0
    assert distance_w5 == 90.0
    assert distance_w1 <= 50.0
    assert distance_w5 > 50.0
    assert distance_w5 <= 120.0


def test_generate_scenario_writes_explicit_physical_vehicles(tmp_path):
    config_path = generate_scenario(
        vehicle_count=50,
        witness_count=5,
        output_dir=tmp_path,
        skip_netconvert=True,
    )

    route_root = ET.parse(tmp_path / "scalable.rou.xml").getroot()
    vehicle_ids = [
        element.attrib["id"]
        for element in route_root.findall("vehicle")
    ]

    assert len(vehicle_ids) == 50
    assert "Vehicle-A" in vehicle_ids
    assert "Witness-W5" in vehicle_ids
    assert config_path == tmp_path.resolve() / "scalable.sumocfg"

    manifest = json.loads(
        (tmp_path / "scenario_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["vehicle_count"] == 50
    assert manifest["witness_count"] == 5
    assert manifest["network_built"] is False
    assert len(manifest["vehicles"]) == 50


def test_road_length_is_large_enough_for_all_depart_positions():
    specs = build_vehicle_specs(
        vehicle_count=500,
        witness_count=5,
        lane_count=4,
    )
    road_length = required_road_length_m(specs)

    assert road_length >= max(
        spec.depart_position_m for spec in specs
    ) + 500.0
