#!/usr/bin/env bash
# Fix common linting errors
set -euxo pipefail

#####################
###### Makefile #####
#####################
mbake format Makefile

################
# Ignore files #
################
bin/sort-ignore.sh

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
if [ "$(find . -type f -name '*Dockerfile' -print -quit)" != "" ]; then
  dockerfmt ./*Dockerfile --write
fi
