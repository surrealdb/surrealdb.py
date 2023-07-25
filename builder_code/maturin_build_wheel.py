#! /usr/bin/env python3

import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Clean up wheels
WHEEL_DIR = ROOT / "target" / "wheels"
if WHEEL_DIR.exists():
    for x in WHEEL_DIR.iterdir():
        x.unlink()

# For macOS and Windows, we run Maturin against the Python interpreter that's
# been installed and configured for this CI run, i.e. the one that's running
# this script. (There are generally several versions installed by default, but
# that's not guaranteed.) For Linux, in order to get "manylinux" compatibility
# right, we need to run Maturin in a special Docker container. We hardcode
# paths to specific interpreter versions, based on where things are installed
# in this container. Our GitHub config has no effect on the the container, so
# we could build all the wheels in one job, but we stick to one-wheel-per-job
# for consistency.
if platform.system() == "Linux":
    version_path_components = {
        (3, 5): ("cp35-cp35m", "xieyanbo/manylinux-maturin:llvm-3.9.1-py-3.5"),
        (3, 6): ("cp36-cp36m", "xieyanbo/manylinux-maturin:llvm-3.9.1"),
        (3, 7): ("cp37-cp37m", "xieyanbo/manylinux-maturin:llvm-3.9.1"),
        (3, 8): ("cp38-cp38", "xieyanbo/manylinux-maturin:llvm-3.9.1"),
        (3, 9): ("cp39-cp39", "xieyanbo/manylinux-maturin:llvm-3.9.1"),
        (3, 10): ("cp310-cp310", "xieyanbo/manylinux-maturin:llvm-3.9.1"),
        # This list needs to be kept in sync with tag.yml.
    }
    (version_component, docker_image) = version_path_components[sys.version_info[:2]]
    interpreter_path = "/opt/python/" + version_component + "/bin/python"
    # See https://github.com/PyO3/maturin#manylinux-and-auditwheel
    command = [
        "docker",
        "run",
        "--rm",
        "--volume=" + os.getcwd() + ":/io",
        docker_image,
        "build",
        "--release",
        "--no-sdist",
        "--manylinux=2014",
        "--interpreter=" + interpreter_path,
    ]
    subprocess.run(command, check=True)
else:
    command = [
        "maturin",
        "build",
        "--release",
        "--no-sdist",
        "--interpreter",
        sys.executable,
    ]
    subprocess.run(command, check=True)

wheels = [x for x in (ROOT / "target" / "wheels").iterdir()]
if len(wheels) != 1:
    raise RuntimeError("expected one wheel, found " + repr(wheels))

print("::set-output name=wheel_path::" + str(wheels[0]))
print("::set-output name=wheel_name::" + wheels[0].name)

