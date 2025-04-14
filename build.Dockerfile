# hadolint ignore=DL3007
FROM nikolaik/python-nodejs:latest
ENV DEBIAN_FRONTEND=noninteractive

USER root
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
  curl \
  gifsicle \
  git \
  libjpeg-progs \
  shellcheck \
  unrar \
  webp \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# hadolint ignore=DL3016
RUN npm install --global svgo

WORKDIR /app
RUN chown circleci:circleci /app
COPY --chown=circleci:circleci bin bin
COPY --chown=circleci:circleci packages packages
RUN bin/mozjpeg.sh
# hadolint ignore=DL3059
RUN bin/pngout.sh

USER circleci
COPY --chown=circleci:circleci pyproject.toml uv.lock package.json package-lock.json ./
RUN npm install

COPY --chown=circleci:circleci . .
RUN mkdir -p test-results dist

# Install
# hadolint ignore=DL3059
RUN uv install
