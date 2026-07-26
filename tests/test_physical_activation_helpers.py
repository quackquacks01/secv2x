from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET

from simulation.sumo.controllers.run_wtc_sumo import (
    count_explicit_route_vehicles,
    resolve_route_files_from_sumocfg,
)


def write_config_and_routes(root: Path, vehicle_count: int) -> Path:
    route_path = root / "scenario.rou.xml"
    routes = ET.Element("routes")
    for index in range(vehicle_count):
        ET.SubElement(routes, "vehicle", {"id": f"v{index}"})
    ET.ElementTree(routes).write(
        route_path,
        encoding="utf-8",
        xml_declaration=True,
    )

    config_path = root / "scenario.sumocfg"
    configuration = ET.Element("configuration")
    input_node = ET.SubElement(configuration, "input")
    ET.SubElement(
        input_node,
        "route-files",
        {"value": route_path.name},
    )
    ET.ElementTree(configuration).write(
        config_path,
        encoding="utf-8",
        xml_declaration=True,
    )
    return config_path


def test_count_explicit_route_vehicles(tmp_path):
    config = write_config_and_routes(tmp_path, 50)

    count, route_files = count_explicit_route_vehicles(config)

    assert count == 50
    assert route_files == [(tmp_path / "scenario.rou.xml").resolve()]


def test_resolve_multiple_route_files(tmp_path):
    first = tmp_path / "a.rou.xml"
    second = tmp_path / "b.rou.xml"
    first.write_text("<routes/>", encoding="utf-8")
    second.write_text("<routes/>", encoding="utf-8")

    configuration = ET.Element("configuration")
    input_node = ET.SubElement(configuration, "input")
    ET.SubElement(
        input_node,
        "route-files",
        {"value": "a.rou.xml,b.rou.xml"},
    )
    config = tmp_path / "scenario.sumocfg"
    ET.ElementTree(configuration).write(
        config,
        encoding="utf-8",
        xml_declaration=True,
    )

    assert resolve_route_files_from_sumocfg(config) == [
        first.resolve(),
        second.resolve(),
    ]
