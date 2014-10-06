picopt
======

A multi-format, recursive, multiprocessor aware, command line image
optimizer utility that uses external tools to do the optimizing.

Picopt depends on Python
`PIL <http://www.pythonware.com/products/pil/>`__ to identify files and
Python `rarfile <https://pypi.python.org/pypi/rarfile>`__ to open CBRs.

To optimize JPEG images. Picopt needs one of
`mozjpeg <https://github.com/mozilla/mozjpeg>`__,
`jpegrescan <https://github.com/kud/jpegrescan>`__ or
`jpegtran <http://jpegclub.org/jpegtran/>`__ on the path. in order of
preferrence.

To optimize lossless images like PNG, PNM, GIF, TIFF and BMP, picopt
requires either `optipng <http://optipng.sourceforge.net/>`__,
`advpng <http://advancemame.sourceforge.net/doc-advpng.html>`__ or
`pngout <http://advsys.net/ken/utils.htm>`__ be on the path. Optipng
provides the most advantage, but best results are acheived by using
pngout as well. Advpng support is disabled by default and must be
explicitly enabled on the command line.

Animated GIFs are optimized with
`gifsicle <http://www.lcdf.org/gifsicle/>`__ if it is available. Picopt
may also nag you to use `HTML5 video <http://gfycat.com/about>`__
instead.

Picopt uncompresses, optimizes and rezips `comic book archive
files <https://en.wikipedia.org/wiki/Comic_book_archive>`__. Be aware
that CBR rar archives will be rezipped into CBZs instead of CBR. Comic
book archive optimization is off by defualt.

Picopt allows you to drop picopt timestamps at the root of your
recursive optimization trees so you don't have to remember which files
to optimize or when you last optimized them.

Installation
------------

Lossless external program packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

OS X
^^^^

::

    brew install optipng pngout jpeg gifsicle

Debian / Ubuntu
^^^^^^^^^^^^^^^

::

    apt-get install optipng pngout libjpeg-progs gifsicle python-imaging

Redhat / Fedora
^^^^^^^^^^^^^^^

::

    yum install optipng pngout libjpeg-progs gifsicle python-imaging

jpegrescan
~~~~~~~~~~

jpegrescan is a better jpeg optimizer than jpegtran, unfortunately it
remains unpackaged :(

::

    git clone git@github.com:kud/jpegrescan.git
    ln -s jpegrescan/jpegrescan /usr/local/bin/jpegrescan

MozJPEG
~~~~~~~

mozjpeg is a better option than even jpegrescan. As of Oct 2014 it may
or may not be packaged for your \*nix, but even when it is, picopt
requires that its separately compiled version of jpegtran be symlinked
to 'mozjpeg' somewhere in the path. This installation example is for OS
X: brew install mozjpeg ln -s /usr/local/Cellar/mozjpeg/2.1/bin/jpegtran
/usr/local/bin/mozjpeg

Picopt
~~~~~~

::

    pip install picopt

Usage
-----

Optimize all JPEG files in a dirctory:

::

    picopt *.jpg

Optimize all files and recurse directories:

::

    picopt -r *

Optimize files and recurse directories AND optimize comic book archives:

::

    picopt -rc *

Optimize files, but not lossless files:

::

    picopt -OPG *

Optimize files, but not jpegs:

::

    picopt -JT *

Optimize files, but not animated gifs:

::

    picopt -G *

Just list files picopt.py would try to optimize:

::

    picopt -l *

Optimize everything in my iPhoto library, but only after the last time i
did this, skipping symlinks to avoid massive amounts of duplicate work.
Don't convert lossless files to PNGs because that would confuse iPhoto.
Also drop a timestamp file so I don't have to remember the last time I
did this:

::

    picopt -rSYt -D '2013 June 1 14:00' 'Pictures/iPhoto Library'

Packaged For
------------

-  `PyPI <https://pypi.python.org/pypi/picopt/>`__
-  `Arch Linux <https://aur.archlinux.org/packages/picopt/>`__

Alternatives
------------

`Imageoptim <http://imageoptim.com/>`__ is an all-in-one OS X GUI
optimizer. Imageoptim command line usage is possible with `an external
program <https://code.google.com/p/imageoptim/issues/detail?can=2&start=0&num=100&q=&colspec=ID%20Type%20Status%20Priority%20Milestone%20Owner%20Summary%20Stars&groupby=&sort=&id=39>`__.
