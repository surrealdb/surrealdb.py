#! /usr/bin/env python3
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).parent.parent

# Workaround for https://github.com/PyO3/maturin/pull/27
shutil.copy2(ROOT / "Cargo.toml", ROOT / "Cargo.toml.orig")

subprocess.run(["maturin", "sdist"])

sdists = [x for x in (ROOT / "target" / "wheels").iterdir()]
if len(sdists) != 1:
    raise RuntimeError("expected one sdist, found " + repr(sdists))

print("::set-output name=sdist_path::" + str(sdists[0]))
print("::set-output name=sdist_name::" + sdists[0].name)

