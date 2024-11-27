.PHONY: test test_versions

test:
	python -m unittest discover -s tests

test_versions:
	python tests/scripts/runner.py
