#!/bin/bash
# mozjpeg
set -euo pipefail

DEB=ci/mozjpeg_3.3.1-1_amd64.deb
dpkg -i "$DEB"
ln -sf /opt/mozjpeg/bin/jpegtran /usr/local/bin/mozjpeg
