# hadolint ignore=DL3007
FROM oven/bun:latest AS bun-source
FROM nikolaik/python-nodejs:python3.14-nodejs24
ENV DEBIAN_FRONTEND=noninteractive

COPY debian.sources /etc/apt/sources.list.d/
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        curl \
        gifsicle \
        jbig2dec \
        shellcheck \
        unrar \
        webp \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=bun-source /usr/local/bin/bun /usr/local/bin/bun
COPY --from=bun-source /usr/local/bin/bunx /usr/local/bin/bunx

# hadolint ignore=DL3016
RUN bun install --global svgo

WORKDIR /app
COPY bin bin
COPY packages packages
# hadolint ignore=DL3059
RUN bin/pngout.sh

COPY pyproject.toml uv.lock package.json package-lock.json ./
RUN bun install

COPY . .
RUN mkdir -p test-results dist

# Install
# hadolint ignore=DL3059
RUN uv sync