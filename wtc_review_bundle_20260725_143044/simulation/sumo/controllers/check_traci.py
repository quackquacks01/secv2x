from __future__ import annotations

import os
from pathlib import Path

import sumolib
import traci


def main() -> None:
    sumo_home = os.environ.get("SUMO_HOME")

    if not sumo_home:
        raise RuntimeError("SUMO_HOME is not configured")

    sumo_binary = Path(sumolib.checkBinary("sumo"))

    if not sumo_binary.exists():
        raise FileNotFoundError(f"SUMO binary not found: {sumo_binary}")

    print(f"SUMO_HOME : {sumo_home}")
    print(f"SUMO      : {sumo_binary}")
    print(f"TraCI     : {traci.__file__}")
    print("SUMO/TRACI ENVIRONMENT: PASS")


if __name__ == "__main__":
    main()