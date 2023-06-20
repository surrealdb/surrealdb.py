#!/usr/bin/env python
from setuptools import setup
from setuptools_rust import Binding, RustExtension

setup(
    name="surrealdb",
    version="1.0",
    rust_extensions=[RustExtension("surrealdb.rust_surrealdb", binding=Binding.PyO3)],
    packages=[
        "surrealdb", 
        "surrealdb.models",
        "surrealdb.execution_descriptors"
    ],
    package_data={
        "surrealdb": ["binaries/*"],
    },
    # rust extensions are not zip safe, just like C-extensions.
    zip_safe=False,
    include_package_data=True
)