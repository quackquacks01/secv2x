from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[3]
    scenario_dir = project_root / "simulation" / "sumo" / "scenarios" / "minimal"

    node_file = scenario_dir / "minimal.nod.xml"
    edge_file = scenario_dir / "minimal.edg.xml"
    net_file = scenario_dir / "minimal.net.xml"
    config_file = scenario_dir / "minimal.sumocfg"

    required = [node_file, edge_file, config_file, scenario_dir / "minimal.rou.xml"]
    missing = [path for path in required if not path.exists()]
    if missing:
        print("Missing scenario files:")
        for path in missing:
            print(f"  - {path}")
        return 1

    netconvert = shutil.which("netconvert")
    if netconvert is None:
        print("ERROR: netconvert was not found in PATH.")
        print('Try: $env:PATH = "C:\\Program Files (x86)\\Eclipse\\Sumo\\bin;$env:PATH"')
        return 1

    command = [
        netconvert,
        "--node-files", str(node_file),
        "--edge-files", str(edge_file),
        "--output-file", str(net_file),
        "--no-turnarounds", "true",
    ]

    print("Running:")
    print(" ".join(command))
    completed = subprocess.run(command, check=False)

    if completed.returncode != 0 or not net_file.exists():
        print("MINIMAL SUMO SCENARIO BUILD: FAIL")
        return 1

    print(f"Generated: {net_file}")
    print(f"Config   : {config_file}")
    print("MINIMAL SUMO SCENARIO BUILD: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
