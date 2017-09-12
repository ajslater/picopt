#!/bin/sh
apt-get install -y python-pip optipng gifsicle

# pngout
wget http://static.jonof.id.au/dl/kenutils/pngout-20150319-linux-static.tar.gz
tar xzf pngout-20150319-linux-static.tar.gz
ln -sf pngout-20150319-linux-static/x86_64/pngout-static /home/ubuntu/bin/pngout

# mozjpeg
wget https://mozjpeg.codelove.de/bin/mozjpeg_3.1_amd64.deb
dpkg -i mozjpeg_3.1_amd64.deb
ln -sf /opt/mozjpeg/bin/jpegtran /home/ubuntu/bin/
