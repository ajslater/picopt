FROM ubuntu:cosmic

RUN apt update
Run apt dist-upgrade -y
RUN apt install -y \
    curl \
    gifsicle \
    git \
    optipng \
    pandoc \
    python-setuptools \
    python3-setuptools \
    unrar
RUN python2 /usr/lib/python2.7/dist-packages/easy_install.py pip
RUN pip install nose
RUN python3 /usr/lib/python3/dist-packages/easy_install.py pip
RUN pip3 install flit nose

# prereqs
WORKDIR /opt/picopt
COPY .git ./.git
RUN git checkout .
RUN ci/mozjpeg.sh
RUN ci/pngout.sh

# Build
RUN bin/pandoc_README.sh

# Build python 2
RUN python2 setup.py build develop

# Build python 3
RUN git add README.rst
RUN flit build
RUN FLIT_ROOT_INSTALL=1 flit install --deps=develop
