#!/bin/bash
# install mozjpeg package and link it
set -euo pipefail

DEB=packages/mozjpeg_4.0.0_amd64.deb
dpkg -i "$DEB"
ln -sf /opt/mozjpeg/bin/jpegtran /usr/local/bin/mozjpeg
