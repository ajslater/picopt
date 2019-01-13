FROM ubuntu:cosmic

RUN apt update
Run apt dist-upgrade -y
RUN apt install -y \
    curl \
    gifsicle \
    optipng \
    pandoc \
    python-setuptools \
    python3-setuptools \
    unrar
RUN python2 /usr/lib/python2.7/dist-packages/easy_install.py pip
RUN pip install nose
RUN python3 /usr/lib/python3/dist-packages/easy_install.py pip
RUN pip3 install nose

# prereqs
WORKDIR /opt/picopt
COPY ci ./ci
COPY bin ./bin
RUN ci/mozjpeg.sh
RUN ci/pngout.sh

COPY requirements* *.py setup.cfg README.md ./

COPY picopt ./picopt
# Build
RUN bin/pandoc_README.sh
RUN python2 setup.py build develop
RUN python3 setup.py build develop
COPY tests ./tests
