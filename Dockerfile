FROM ubuntu:bionic

RUN apt update
Run apt dist-upgrade
RUN apt install -y optipng gifsicle unrar curl python-setuptools
RUN python /usr/lib/python2.7/dist-packages/easy_install.py pip

COPY requirements* *.py setup.cfg README.rst ./
COPY picopt ./picopt
COPY tests ./tests
COPY ci ./ci

# Install software
RUN ci/pngout.sh
RUN ci/mozjpeg.sh

# Build
RUN pip install nose
RUN ./setup.py build develop
