FROM cimg/python:3.9-node
#FROM ajslater/picopt-builder:latest

ENV DEBIAN_FRONTEND noninteractive

USER root
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get dist-upgrade -y \
    && apt-get install -y --no-install-recommends \
        curl \
        gifsicle \
        git \
        libjpeg-progs \
        optipng \
        shellcheck \
#        python3-setuptools \
#        python3-venv \
        unrar \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=circleci:circleci ci ci
RUN ci/mozjpeg.sh
RUN ci/pngout.sh

USER circleci
# hadolint ignore=DL3013
RUN pip3 install poetry
# hadolint ignore=DL3016
RUN npm install

COPY --chown=circleci:circleci . .
RUN mkdir -p test-results dist

# Install
RUN poetry install
