#!/usr/bin/env python
import os
import re

from setuptools import setup


def get_package_version(package: str) -> str:
    with open(os.path.join(package, "__init__.py")) as f:
        version = re.search(r"__version__ = \"(.*?)\"", f.read()).group(1)

    return version


def get_readme() -> str:
    with open("README.md") as f:
        return f.read()


setup(
    name="surrealdb",
    version=get_package_version("surrealdb"),
    license="Apache-2.0",
    python_requires=">=3.7",
    url="https://github.com/surrealdb/surrealdb.py",
    description="The official SurrealDB library for Python.",
    long_description=get_readme(),
    long_description_content_type="text/markdown",
    package_data={"surrealdb": ["py.typed"]},
    install_requires=["httpx>=0.23.0", "requests>=2.28.1"],
    extras_require={"speedup": ["orjson>=3.8.0"]},
    classifiers=[
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3 :: Only",
    ],
)
