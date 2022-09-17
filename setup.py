from setuptools import setup, find_packages

setup(
    name='surrealdb',
    version='0.1',
    packages=find_packages(include=["surrealdb"]),
    install_requires=["urllib3"],
    author='ayonull',
)