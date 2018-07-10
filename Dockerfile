FROM ubuntu:bionic

RUN apt update
Run apt dist-upgrade -y
RUN apt install -y optipng gifsicle unrar curl python-setuptools pandoc
RUN python /usr/lib/python2.7/dist-packages/easy_install.py pip

COPY requirements* *.py setup.cfg README.md ./
COPY picopt ./picopt
COPY tests ./tests
COPY ci ./ci
COPY bin ./bin

# Install software
RUN ci/pngout.sh
RUN ci/mozjpeg.sh
RUN pip install nose

# Build
RUN bin/pandoc_README.sh
RUN ./setup.py build develop
