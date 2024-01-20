#!/bin/bash
# install oxipng binary
set -euo pipefail

RELEASE=9.0.0
ARCH=$(arch)
DIR_NAME=oxipng-${RELEASE}-${ARCH}-unknown-linux-gnu
TARBALL=${DIR_NAME}.tar.gz
URL=https://github.com/shssoichiro/oxipng/releases/download/v${RELEASE}/${TARBALL}
BIN_NAME=$DIR_NAME/oxipng
DEST=/usr/local/bin/oxipng

if [ -f "$TARBALL" ]; then
  echo "$TARBALL > $DEST"
  tar xzOf "$TARBALL" "$BIN_NAME" > "$DEST"
else
  echo "$URL > $DEST"
  curl "$URL" | tar xzOf - "$BIN_NAME" > "$DEST"
fi
chmod 755 "$DEST"
