from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def copy_tree(source_root: Path, project_root: Path) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for source in source_root.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(source_root)
        if relative.name in {"README_KO.txt"}:
            continue
        target = project_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            backup = target.with_name(f"{target.name}.bak_{timestamp}")
            shutil.copy2(target, backup)
            print(f"Backup: {backup}")

        shutil.copy2(source, target)
        print(f"Copied: {relative}")


def run(command: list[str], cwd: Path) -> int:
    print("\n>", " ".join(command))
    return subprocess.run(command, cwd=cwd, check=False).returncode


def main() -> int:
    source_root = Path(__file__).resolve().parent
    project_root = Path.cwd()

    if not (project_root / "pyproject.toml").exists():
        print("ERROR: Run this script from the secv2x project root.")
        print(r'Example: Set-Location "C:\Users\wah43\secv2x"')
        return 1

    copy_tree(source_root, project_root)

    commands = [
        [sys.executable, "-m", "pytest", "-q", "tests/test_sumo_minimal_files.py"],
        [sys.executable, "-m", "simulation.sumo.controllers.build_minimal_scenario"],
        [sys.executable, "-m", "simulation.sumo.controllers.run_minimal", "--steps", "30"],
    ]

    for command in commands:
        if run(command, project_root) != 0:
            print("\nMINIMAL SUMO SETUP: FAIL")
            return 1

    print("\nMINIMAL SUMO SETUP: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
