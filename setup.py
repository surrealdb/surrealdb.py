#!/usr/bin/env python
from setuptools import setup
from setuptools_rust import Binding, RustExtension

import os
import subprocess

# Install LLVM using pip
install_pip = subprocess.Popen(["sudo apt-get install -y python3-pip"], shell=True)
install_pip.wait()

# Install LLVM using pip
install_llvm = subprocess.Popen(["sudo pip3 install llvmlite"], shell=True)
install_llvm.wait()

# Get the LLVM library path
llvm_lib_path = subprocess.check_output(["llvm-config", "--libdir"]).decode().strip()

# Set the LIBCLANG_PATH environment variable
os.environ["LIBCLANG_PATH"] = llvm_lib_path


setup(
    name="surrealdb",
    version="1.0",
    rust_extensions=[RustExtension("surrealdb.rust_surrealdb", binding=Binding.PyO3)],
    packages=[
        "surrealdb", 
        "surrealdb.models",
        "surrealdb.execution_mixins"
    ],
    package_data={
        "surrealdb": ["binaries/*"],
    },
    # rust extensions are not zip safe, just like C-extensions.
    zip_safe=False,
    include_package_data=True
)