FROM ubuntu:impish

ENV DEBIAN_FRONTEND noninteractive

# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        gifsicle \
        libjpeg-progs \
        optipng \
        python3-pip \
        unrar \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /
COPY --chown=circleci:circleci ci ci
RUN ci/mozjpeg.sh
# hadolint ignore=DL3059
RUN ci/pngout.sh

# hadolint ignore=DL3059,DL3013
RUN pip3 install --no-cache-dir -U picopt
CMD ["picopt", "-h"]
