#!/usr/bin/env python
import pathlib

from setuptools import setup


with open("README.md", "r") as fh:
    long_description = fh.read()


with open(str(pathlib.Path(__file__).parent.absolute()) + "/surrealdb/VERSION.txt", "r") as fh:
    version = fh.read().split("=")[1].replace("'", "")


setup(
    name="surrealdb-beta",
    author="Maxwell Flitton",
    author_email="maxwell@gmail.com",
    description="SurrealDB python client.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    version=version,
    packages=[
        "surrealdb",
        "surrealdb.data",
        "surrealdb.data.types"
    ],
    package_data={
        "surrealdb": ["binaries/*"],
    },
    install_requires=[
        "cbor2==5.6.5",
        "certifi==2024.12.14",
        "charset-normalizer==3.4.0",
        "idna==3.10",
        "pytz==2024.2",
        "requests==2.32.3",
        "semantic-version==2.10.0",
        "tomli==2.2.1",
        "types-pytz==2024.2.0.20241003",
        "types-requests==2.32.0.20241016",
        "typing_extensions==4.12.2",
        "urllib3==2.2.3",
        "websockets==14.1",
    ],
    # rust extensions are not zip safe, just like C-extensions.
    zip_safe=False,
    include_package_data=True
)
