picopt
======

A multi format recursive image optimizer that uses external tools.
Picopt also uncompresses, optimizes and rezips [comic book archive files](https://en.wikipedia.org/wiki/Comic_book_archive).

Picopt depends on Python [PIL](http://www.pythonware.com/products/pil/) to identify files and [rarfile](https://pypi.python.org/pypi/rarfile) to open CBRs.

To optimize JPEG images. Picopt needs either [jpegrescan](https://github.com/kud/jpegrescan) or [jpegtran](http://jpegclub.org/jpegtran/) on the path. jpegrescan is preferred.

To optimize lossless images like PNG, PNM, GIF, TIFF and BMP, picopt requires either [optipng](http://optipng.sourceforge.net/) or [pngout](http://advsys.net/ken/utils.htm) be on the path. optipng provides the most advantage, but best results are acheived by using both utilities.

Animated GIFs are optimized with [gifsicle](http://www.lcdf.org/gifsicle/) if it is available.

Installation
------------

### Lossless external programs
#### OS X
    brew install optipng pngout jpeg gifsicle

#### Debian / Ubuntu
    apt-get install optipng pngout libjpeg-progs gifsicle

#### Redhat / Fedora
    yum install optipng pngout libjpeg-progs gifsicle

### jpegrescan
    git clone git@github.com:kud/jpegrescan.git
    ln -s jpegrescan/jpegrescan /usr/local/bin/jpegrescan

### Picopt
    git clone git@github.com:ajslater/picopt.git
    cd picopt

    pip install -r requirements.txt
    pip install .

    picopt.py -h
