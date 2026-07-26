from pathlib import Path
import sys
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
FILES = [
    "capture.nod.xml",
    "capture.edg.xml",
    "capture.net.xml",
    "capture.rou.xml",
    "capture.add.xml",
    "capture.view.xml",
    "capture.sumocfg",
]

errors = []
for name in FILES:
    path = BASE / name
    if not path.exists():
        errors.append(f"missing file: {name}")
        continue
    try:
        ET.parse(path)
    except ET.ParseError as exc:
        errors.append(f"XML parse error in {name}: {exc}")

if errors:
    print("\n".join(errors))
    sys.exit(1)

net_root = ET.parse(BASE / "capture.net.xml").getroot()
edge_info = {}
lane_info = {}
for edge in net_root.findall("edge"):
    if edge.get("function"):
        continue
    lanes = edge.findall("lane")
    edge_info[edge.get("id")] = {
        "from": edge.get("from"),
        "to": edge.get("to"),
        "lanes": [lane.get("id") for lane in lanes],
    }
    for lane in lanes:
        lane_info[lane.get("id")] = float(lane.get("length"))

route_root = ET.parse(BASE / "capture.rou.xml").getroot()
route_map = {}
for route in route_root.findall("route"):
    edges = route.get("edges", "").split()
    route_map[route.get("id")] = edges
    for edge_id in edges:
        if edge_id not in edge_info:
            errors.append(f"route {route.get('id')} references missing edge {edge_id}")
    for left, right in zip(edges, edges[1:]):
        if left in edge_info and right in edge_info:
            if edge_info[left]["to"] != edge_info[right]["from"]:
                errors.append(f"disconnected route {route.get('id')}: {left} -> {right}")

types = {v.get("id"): v for v in route_root.findall("vType")}
for type_id, vtype in types.items():
    if not vtype.get("guiShape"):
        errors.append(f"vType {type_id} has no guiShape")

vehicle_ids = set()
for vehicle in route_root.findall("vehicle"):
    vid = vehicle.get("id")
    if vid in vehicle_ids:
        errors.append(f"duplicate vehicle id: {vid}")
    vehicle_ids.add(vid)

    route_id = vehicle.get("route")
    edges = route_map.get(route_id, [])
    if not edges:
        errors.append(f"vehicle {vid} references missing/empty route {route_id}")
        continue

    first_edge = edges[0]
    lane_index = int(vehicle.get("departLane", "0"))
    lanes = edge_info[first_edge]["lanes"]
    if lane_index < 0 or lane_index >= len(lanes):
        errors.append(f"vehicle {vid}: departLane={lane_index} invalid on {first_edge}")
    else:
        lane_id = lanes[lane_index]
        depart_pos = float(vehicle.get("departPos", "0"))
        if depart_pos > lane_info[lane_id]:
            errors.append(
                f"vehicle {vid}: departPos={depart_pos} exceeds {lane_id} length={lane_info[lane_id]}"
            )

    for stop in vehicle.findall("stop"):
        lane_id = stop.get("lane")
        if lane_id not in lane_info:
            errors.append(f"vehicle {vid}: stop references missing lane {lane_id}")
            continue
        start_pos = float(stop.get("startPos", "0"))
        end_pos = float(stop.get("endPos", "0"))
        if not (0 <= start_pos <= end_pos <= lane_info[lane_id]):
            errors.append(
                f"vehicle {vid}: stop {lane_id} range {start_pos}..{end_pos} "
                f"outside lane length {lane_info[lane_id]}"
            )

if errors:
    print("STATIC VALIDATION FAILED")
    for err in errors:
        print(" -", err)
    sys.exit(1)

print("STATIC VALIDATION PASSED")
print(f" - files: {len(FILES)}")
print(f" - normal edges: {len(edge_info)}")
print(f" - lanes: {len(lane_info)}")
print(f" - routes: {len(route_map)}")
print(f" - vehicles: {len(vehicle_ids)}")
print("Next: run 'sumo -c capture.sumocfg --check-route true'.")
