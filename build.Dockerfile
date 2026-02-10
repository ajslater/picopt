# hadolint ignore=DL3007
FROM nikolaik/python-nodejs:python3.13-nodejs24
ENV DEBIAN_FRONTEND=noninteractive

COPY debian.sources /etc/apt/sources.list.d/
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        curl \
        gifsicle \
        shellcheck \
        unrar \
        webp \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# hadolint ignore=DL3016
RUN npm install --global svgo

WORKDIR /app
COPY bin bin
COPY packages packages
# hadolint ignore=DL3059
RUN bin/pngout.sh

COPY pyproject.toml uv.lock package.json package-lock.json ./
RUN npm install

COPY . .
RUN mkdir -p test-results dist

# Install
# hadolint ignore=DL3059
RUN uv sync