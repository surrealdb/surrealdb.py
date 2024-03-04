#!/usr/bin/env python
import pathlib

from setuptools import setup
from setuptools_rust import Binding, RustExtension


with open("README.md", "r") as fh:
    long_description = fh.read()


with open(str(pathlib.Path(__file__).parent.absolute()) + "/surrealdb/VERSION.txt", "r") as fh:
    version = fh.read().split("=")[1].replace("'", "")


setup(
    name="surrealdb-beta",
    author="Maxwell Flitton",
    author_email="maxwell@gmail.com",
    description="SurrealDB python client written in Rust.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    version=version,
    rust_extensions=[RustExtension("surrealdb.rust_surrealdb", binding=Binding.PyO3)],
    packages=[
        "surrealdb",
        "surrealdb.execution_mixins",
        "surrealdb.async_execution_mixins"
    ],
    package_data={
        "surrealdb": ["binaries/*"],
    },
    # rust extensions are not zip safe, just like C-extensions.
    zip_safe=False,
    include_package_data=True
)
