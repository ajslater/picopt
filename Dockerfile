FROM ubuntu:mantic

ENV DEBIAN_FRONTEND noninteractive

# hadolint ignore=DL3008
RUN apt-get update \
  && apt-get upgrade -y \
  && apt-get install -y --no-install-recommends \
    gifsicle \
    libjpeg-progs \
    python3-pip \
    unrar \
    webp \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# hadolint ignore=DL3016
RUN npm install svgo

WORKDIR /
COPY --chown=circleci:circleci in bin
COPY --chown=circleci:circleci packages packages
RUN bin/mozjpeg.sh
# hadolint ignore=DL3059
RUN bin/oxipng.sh
# hadolint ignore=DL3059
RUN bin/pngout.sh

# hadolint ignore=DL3059,DL3013
RUN pip3 install --no-cache-dir -U picopt
CMD ["picopt", "-h"]
