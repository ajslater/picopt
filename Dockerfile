# hadolint ignore=DL3007
FROM oven/bun:latest AS bun-source
FROM nikolaik/python-nodejs:python3.15-nodejs26
ENV DEBIAN_FRONTEND=noninteractive

COPY debian.sources /etc/apt/sources.list.d/
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        curl \
        gifsicle \
        jbig2dec \
        poppler-utils \
        unrar \
        webp \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=bun-source /usr/local/bin/bun /usr/local/bin/bun
COPY --from=bun-source /usr/local/bin/bunx /usr/local/bin/bunx

# Lint tools devenv's bin/ scripts run, unpinned on purpose.
COPY --from=koalaman/shellcheck:stable /bin/shellcheck /usr/local/bin/
COPY --from=mvdan/shfmt:latest /bin/shfmt /usr/local/bin/
COPY --from=hadolint/hadolint:latest /bin/hadolint /usr/local/bin/
COPY --from=rhysd/actionlint:latest /usr/local/bin/actionlint /usr/local/bin/
COPY --from=ghcr.io/reteps/dockerfmt:latest /ko-app/dockerfmt /usr/local/bin/
ADD https://github.com/anordal/shellharden/releases/latest/download/shellharden-x86_64-unknown-linux-musl.tar.gz /tmp/shellharden.tar.gz
RUN tar -xzf /tmp/shellharden.tar.gz -C /usr/local/bin shellharden && rm /tmp/shellharden.tar.gz

WORKDIR /app
COPY bin bin
COPY packages packages
# hadolint ignore=DL3059
RUN bin/pngout.sh

COPY bun.lock package.json ./
RUN bun install

COPY . .
RUN mkdir -p test-results dist

# Install
# hadolint ignore=DL3059
RUN make install