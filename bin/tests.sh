#!/bin/sh
mkdir -p test-results
poetry run coverage run -m pytest --junitxml=test-results/junit.xml
poetry run coverage combine
poetry run coverage report
poetry run coverage xml
poetry run coverage html
poetry run mypy picopt tests
