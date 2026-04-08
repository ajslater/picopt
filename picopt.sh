#!/usr/bin/env bash
# Run picopt in development
export PYTHONDEVMODE=1
uv run ./picopt.py "$@"
