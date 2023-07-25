# This script is for printing debug information in CI, to help with tracking
# down configuration errosr. It's similar to what PyO3 use to detect the Python
# version.

import sys
import sysconfig
import platform
import json

PYPY = platform.python_implementation() == "PyPy"

try:
    base_prefix = sys.base_prefix
except AttributeError:
    base_prefix = sys.exec_prefix

info = {
    "version": {
        "major": sys.version_info[0],
        "minor": sys.version_info[1],
        "implementation": platform.python_implementation()
    },
    "libdir":
    sysconfig.get_config_var('LIBDIR'),
    "ld_version":
    sysconfig.get_config_var('LDVERSION')
    or sysconfig.get_config_var('py_version_short'),
    "base_prefix":
    base_prefix,
    "shared":
    PYPY or bool(sysconfig.get_config_var('Py_ENABLE_SHARED')),
    "executable":
    sys.executable,
    "machine":
    platform.machine(),
    "maxsize_bits":
    sys.maxsize.bit_length(),
    "architecture":
    platform.architecture(),
    "platform":
    platform.platform(),
}

print(json.dumps(info, indent="  "))
