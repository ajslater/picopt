FROM ubuntu:cosmic

RUN apt update
Run apt dist-upgrade -y
RUN apt install -y optipng gifsicle unrar curl python-setuptools pandoc #python3-setuptools
RUN python2 /usr/lib/python2.7/dist-packages/easy_install.py pip
#RUN python3 /usr/lib/python3/dist-packages/easy_install.py pip
RUN pip install nose
#RUN pip3 install nose

# prereqs
COPY ci ./ci
COPY bin ./bin
RUN ci/mozjpeg.sh
RUN ci/pngout.sh

COPY requirements* *.py setup.cfg README.md ./

COPY picopt ./picopt
RUN bin/pandoc_README.sh
RUN python setup.py build develop
#RUN python3 setup.py build develop
COPY tests ./tests

# Build
RUN nosetests-2.7
#RUN nosetests-3.4
