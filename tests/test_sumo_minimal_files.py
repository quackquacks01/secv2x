from pathlib import Path
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = PROJECT_ROOT / "simulation" / "sumo" / "scenarios" / "minimal"


def test_minimal_sumo_source_files_exist():
    expected = [
        "minimal.nod.xml",
        "minimal.edg.xml",
        "minimal.rou.xml",
        "minimal.sumocfg",
    ]
    for name in expected:
        assert (SCENARIO_DIR / name).exists(), name


def test_minimal_route_contains_expected_vehicles():
    root = ET.parse(SCENARIO_DIR / "minimal.rou.xml").getroot()
    vehicle_ids = {element.attrib["id"] for element in root.findall("vehicle")}
    assert vehicle_ids == {"Vehicle-A", "Witness-W1", "Witness-W2"}


def test_minimal_config_references_expected_files():
    root = ET.parse(SCENARIO_DIR / "minimal.sumocfg").getroot()
    net_file = root.find("./input/net-file")
    route_files = root.find("./input/route-files")
    assert net_file is not None
    assert route_files is not None
    assert net_file.attrib["value"] == "minimal.net.xml"
    assert route_files.attrib["value"] == "minimal.rou.xml"
