#!/bin/bash
# pngout
set -euo pipefail

URL=http://static.jonof.id.au/dl/kenutils/pngout-20150319-linux-static.tar.gz 
TARBALL=/tmp/pngout.tar.gz
CONTENTS=/tmp/pngout-20150319-linux-static

curl -o "$TARBALL" "$URL"

tar xzf "$TARBALL"
mv "$CONTENTS/x86_64/pngout-static" /usr/local/bin/pngout
rm -rf "$TARBALL" "$CONTENTS"
