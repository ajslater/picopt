#!/bin/bash
# mozjpeg
set -euo pipefail

DEB=mozjpeg_3.1_amd64.deb
URL="https://mozjpeg.codelove.de/bin/$DEB"

cd /tmp

wget "$URL"
sudo dpkg -i "$DEB"
sudo ln -sf /opt/mozjpeg/bin/jpegtran /usr/local/bin/mozjpeg
rm -f "$DEB"
