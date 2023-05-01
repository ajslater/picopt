#!/bin/bash
# create monkeytype db
poetry run pytest --monkeytype-output=./monkeytype.sqlite3
