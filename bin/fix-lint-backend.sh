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
poetry run ruff check --fix .
poetry run ruff format .
# poetry run djlint templates --profile=django --reformat

############################################
##### Javascript, JSON, Markdown, YAML #####
############################################
npm run fix

###################
###### Shell ######
###################
shellharden --replace ./**/*.sh
