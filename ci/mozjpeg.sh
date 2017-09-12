#!/bin/sh
# mozjpeg
cd /tmp
wget https://mozjpeg.codelove.de/bin/mozjpeg_3.1_amd64.deb
sudo dpkg -i mozjpeg_3.1_amd64.deb
sudo ln -sf /opt/mozjpeg/bin/jpegtran /usr/local/bin/mozjpeg
