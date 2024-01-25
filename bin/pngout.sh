#!/bin/bash
# install pngout binary
set -euo pipefail

RELEASE=pngout-20200115-linux-static
URL=http://static.jonof.id.au/dl/kenutils/$RELEASE.tar.gz
TARBALL="packages/$RELEASE.tar.gz"
BIN_NAME=$RELEASE/amd64/pngout-static
DEST=/usr/local/bin/pngout

if [ -f "$TARBALL" ]; then
  echo "$TARBALL > $DEST"
  tar xzOf "$TARBALL" "$BIN_NAME" > "$DEST"
else
  echo "$URL > $DEST"
  curl "$URL" | tar xzOf - "$BIN_NAME" > "$DEST"
fi
chmod 755 "$DEST"
