from __future__ import annotations

import platform
import shutil
import struct
import sys


def yes_no(value: bool) -> str:
    return "OK" if value else "MISSING"


print("=== Python environment check ===")
print("Python       :", sys.version.replace("\n", " "))
print("Executable   :", sys.executable)
print("OS           :", platform.platform())
print("Architecture :", platform.machine())
print("Pointer bits :", struct.calcsize("P") * 8)
print("git          :", yes_no(shutil.which("git") is not None))
print("gcc          :", yes_no(shutil.which("gcc") is not None))
print("clang        :", yes_no(shutil.which("clang") is not None))
print("cmake        :", yes_no(shutil.which("cmake") is not None))
print("make         :", yes_no(shutil.which("make") is not None))

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required.")

print("\nEnvironment check completed.")
