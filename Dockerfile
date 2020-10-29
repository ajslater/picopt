FROM ajslater/picopt-builder:latest

ENV DEBIAN_FRONTEND noninteractive

# hadolint ignore=DL3008
USER root
RUN apt-get update \
    && apt-get dist-upgrade -y \
    && apt-get install -y --no-install-recommends \
        curl \
        gifsicle \
        git \
        libjpeg-progs \
        optipng \
        python3-setuptools \
        python3-venv \
        unrar \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

#RUN python3 /usr/lib/python3/dist-packages/easy_install.py pip
USER circleci
# hadolint ignore=DL3013
RUN pip3 install poetry
COPY ci ci

USER root
RUN ci/mozjpeg.sh
RUN ci/pngout.sh

USER circleci
COPY . .

# Install
RUN poetry install
