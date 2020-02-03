FROM ubuntu:19.10

ENV DEBIAN_FRONTEND noninteractive

# hadolint ignore=DL3008
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

RUN python3 /usr/lib/python3/dist-packages/easy_install.py pip
# hadolint ignore=DL3013
RUN pip3 install poetry
WORKDIR /opt/picopt/
COPY ci ci
RUN ci/mozjpeg.sh
RUN ci/pngout.sh
COPY . .

# Install
RUN poetry install
