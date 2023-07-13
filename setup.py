#!/usr/bin/env python
from setuptools import setup
from setuptools_rust import Binding, RustExtension

# import subprocess
# import sys

# def install_package(package):
#     subprocess.check_call([sys.executable, "-m", "pip", "install", package])


# install_package("libclang")


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