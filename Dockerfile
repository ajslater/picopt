FROM ubuntu:groovy

ENV DEBIAN_FRONTEND noninteractive

# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get dist-upgrade -y \
    && apt-get install -y --no-install-recommends \
        gifsicle \
        libjpeg-progs \
        optipng \
        python3-pip \
        unrar \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=circleci:circleci ci ci
RUN ci/mozjpeg.sh
RUN ci/pngout.sh

RUN pip3 install picopt
CMD picopt -h
