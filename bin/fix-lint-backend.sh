#!/bin/bash
# Fix common linting errors
set -euxo pipefail

################
# Ignore files #
################
bin/sortignore.sh

####################
###### Python ######
###################
uv run --group lint ruff check --fix .
uv run --group lint ruff format .
# uv run --group lint djlint templates --profile=django --reformat

############################################
##### Javascript, JSON, Markdown, YAML #####
############################################
npm run fix

###################
###### Shell ######
###################
shellharden --replace ./**/*.sh

#######################
###### Dockerfile #####
#######################
dockerfmt ./*Dockerfile --write
