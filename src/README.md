# Building a distribution
We can build a distribution with the following command:

```python
python setup.py bdist_wheel
```

This will give a lengthy printout resulting in a `build` directory which will not need to be kept and a `dist` directory
which will carry our package to be installed. We can then install the package we need with the following command:

```python
pip install dist/surrealdb-1.0-cp39-cp39-macosx_13_0_universal2.whl
```
And this will result in being installed. 
