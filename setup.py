#!/usr/bin/env python
import pathlib

from setuptools import setup


with open("README.md", "r") as fh:
    long_description = fh.read()


with open(str(pathlib.Path(__file__).parent.absolute()) + "/surrealdb/VERSION.txt", "r") as fh:
    version = fh.read().split("=")[1].replace("'", "")


setup(
    name="surrealdb",
    author="SurrealDB",
    author_email="maxwell@gmail.com",
    description="SurrealDB python client.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    version=version,
    # package_dir={"surrealdb": "surrealdb"},
    packages=[
        "surrealdb",
        "surrealdb.data",
        "surrealdb.data.types",
    ],
    package_data={
        "surrealdb": ["binaries/*"],
    },
    # rust extensions are not zip safe, just like C-extensions.
    zip_safe=False,
    include_package_data=True
)
