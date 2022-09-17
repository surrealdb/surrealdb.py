# surrealdb.py

The official SurrealDB library for Python.

[![](https://img.shields.io/badge/status-beta-ff00bb.svg?style=flat-square)](https://github.com/surrealdb/surrealdb.py) [![](https://img.shields.io/badge/docs-view-44cc11.svg?style=flat-square)](https://surrealdb.com/docs/integration/libraries/python) [![](https://img.shields.io/badge/license-Apache_License_2.0-00bfff.svg?style=flat-square)](https://github.com/surrealdb/surrealdb.py)


## To build

In the folder do
(If python3 does not work, do python) 

```python3 -m pip install urllib3 wheel```

Then

```python3 setup.py bdist_wheel```

Once it finishes building, please go to the dist folder and do

```python3 -m pip install surrealdb-(version)-py3-none-any.whl```
