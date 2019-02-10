#!/bin/bash
# pngout
set -euo pipefail

URL=http://static.jonof.id.au/dl/kenutils/pngout-20150319-linux-static.tar.gz 
TARBALL="$(dirname "$0")/pngout-20150319-linux-static.tar.gz"
BIN_NAME=pngout-20150319-linux-static/x86_64/pngout-static
DEST=/usr/local/bin/pngout

if [ -f "$TARBALL" ]; then
    echo "$TARBALL > $DEST"
    tar xzOf "$TARBALL" $BIN_NAME > $DEST
else
    echo "$URL > $DEST"
    curl "$URL" | tar xzOf - $BIN_NAME > $DEST
fi
chmod 755 "$DEST"
