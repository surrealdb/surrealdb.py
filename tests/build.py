#! /usr/bin/env python3

# Build the shared library, and then copy it into this directory, so that
# test_rocksdb.py can see it. We use the filename that Python requires on the
# curent platform: rocksdb3.so on Linux and macOS, and rocksdb3.pyd on Windows.

import os
from pathlib import Path
import platform
import shutil
import subprocess

HERE = Path(__file__).parent
ROOT = HERE / ".."

subprocess.run(["cargo", "build", "--release"], check=True, cwd=str(ROOT))

if platform.system() == "Windows":
    SRC_NAME = "rocksdb3.dll"
    DEST_NAME = "rocksdb3.pyd"
elif platform.system() == "Darwin":
    SRC_NAME = "librocksdb3.dylib"
    DEST_NAME = "rocksdb3.so"
else:
    # Assume everything else behaves like Linux.
    SRC_NAME = "librocksdb3.so"
    DEST_NAME = "rocksdb3.so"

source_path = ROOT / "target"
cargo_build_target = os.environ.get("CARGO_BUILD_TARGET")
if cargo_build_target:
    source_path = source_path / cargo_build_target
source_path = source_path / "release" / SRC_NAME
destination_path = HERE / DEST_NAME
print("copying", source_path, "to", destination_path)
shutil.copy2(str(source_path), str(destination_path))
