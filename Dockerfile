FROM ubuntu:cosmic

RUN apt update
Run apt dist-upgrade -y
RUN apt install -y \
    curl \
    gifsicle \
    git \
    optipng \
    pandoc \
    python3-setuptools \
    unrar
RUN python3 /usr/lib/python3/dist-packages/easy_install.py pip
RUN pip3 install flit

# prereqs
WORKDIR /opt/picopt
COPY ci ./ci
COPY bin ./bin
RUN ci/mozjpeg.sh
RUN ci/pngout.sh

COPY pyproject.toml README.md ./
# TODO ends up with unchecked out vcs errors
COPY .git ./.git
COPY picopt ./picopt

# Build
RUN bin/pandoc_README.sh
RUN flit build
RUN flit install --deps=develop
COPY tests ./tests
