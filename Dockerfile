FROM ubuntu:eoan

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
RUN pip3 install poetry nose

# prereqs
WORKDIR /opt/picopt
COPY .git ./.git
RUN git checkout master .
RUN ci/mozjpeg.sh
RUN ci/pngout.sh

# Build
RUN bin/pandoc_README.sh

# Build python 3
RUN git add README.rst
RUN poetry install
RUN poetry build
RUN poetry install
