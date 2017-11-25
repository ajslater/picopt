picopt
======

A multi-format, recursive, multiprocessor aware, command line lossless
image optimizer utility that uses external tools to do the optimizing.

Picopt depends on Python
`PIL <http://www.pythonware.com/products/pil/>`__ to identify files and
Python `rarfile <https://pypi.python.org/pypi/rarfile>`__ to open CBRs.

The actual image optimization is accomplished by external programs.

To optimize JPEG images. Picopt needs one of
`mozjpeg <https://github.com/mozilla/mozjpeg>`__,
`jpegrescan <https://github.com/kud/jpegrescan>`__ or
`jpegtran <http://jpegclub.org/jpegtran/>`__ on the path. in order of
preference.

To optimize lossless images like PNG, PNM, GIF, and BMP, picopt requires
either `optipng <http://optipng.sourceforge.net/>`__,
`advpng <http://advancemame.sourceforge.net/doc-advpng.html>`__ or
`pngout <http://advsys.net/ken/utils.htm>`__ be on the path. Optipng
provides the most advantage, but best results are acheived by using
pngout as well. Advpng support is disabled by default and must be
explicitly enabled on the command line.

Animated GIFs are optimized with
`gifsicle <http://www.lcdf.org/gifsicle/>`__ if it is available. Picopt
nag you to convert your file to `HTML5
video <http://gfycat.com/about>`__, but does not provide this service
itself.

Picopt uncompresses, optimizes and rezips `comic book archive
files <https://en.wikipedia.org/wiki/Comic_book_archive>`__. Be aware
that CBR rar archives will be rezipped into CBZs instead of CBR. Comic
book archive optimization is not turned on by default to prevent
surprises.

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

    brew install optipng mozjpeg gifsicle
    ln -s /usr/local/Cellar/mozjpeg/3.1/bin/jpegtran /usr/local/bin/mozjpeg

Debian / Ubuntu
^^^^^^^^^^^^^^^

::

    apt-get install optipng gifsicle python-imaging

if you don't want to install mozjpeg using the instructions below then
use jpegtran:

::

    apt-get install libjpeg-progs

Redhat / Fedora
^^^^^^^^^^^^^^^

::

    yum install optipng gifsicle python-imaging

if you don't want to install mozjpeg using the instructions below then
use jpegtran:

::

    yum install libjpeg-progs

MozJPEG
^^^^^^^

mozjpeg offers better compression than libjpeg-progs' jpegtran. As of
Oct 2015 it may or may not be packaged for your \*nix, but even when it
is, picopt requires that its separately compiled version of jpegtran be
symlinked to 'mozjpeg' somewhere in the path. This installation example
is for OS X:

::

    ln -s /usr/local/Cellar/mozjpeg/3.1/bin/jpegtran /usr/local/bin/mozjpeg

You may find Linux instructions at `Robert Walter's
Blog <http://www.robertwalter.de/blog/2015/04/08/mozjpeg-3-0-0-on-debian-and-ubuntu/>`__

jpegrescan
^^^^^^^^^^

If you can't install MozJPEG, jpegrescan is a better jpeg optimizer than
jpegtran contained in libjpeg-progs, unfortunately it also remains
unpackaged :(

::

    git clone git@github.com:kud/jpegrescan.git
    ln -s jpegrescan/jpegrescan /usr/local/bin/jpegrescan

pngout
^^^^^^

pngout is a useful compression to use after optipng. It is not packaged,
but you may find the latest binary version `on JonoF's
site <http://www.jonof.id.au/kenutils>`__

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

Gotchas
-------

Picopt automatically uses timestamp files if it detects them in or above
the current directory tree. A situation can arise with comic archives
where the comic archive itself is newer than the timestamp file so it is
processed, but the files inside the archive are older than the timestamp
file so they are not. Currently the workaround is to move the comic
archive outside of the current tree into a temporary directory and
process it there.

Packaged For
------------

-  `PyPI <https://pypi.python.org/pypi/picopt/>`__
-  `Arch Linux <https://aur.archlinux.org/packages/picopt/>`__

Alternatives
------------

`imagemin <https://github.com/imagemin/imagemin-cli>`__ looks to be an
all in one cli and gui solution with bundled libraries, so no awkward
dependancies. `Imageoptim <http://imageoptim.com/>`__ is an all-in-one
OS X GUI image optimizer. Imageoptim command line usage is possible with
`an external
program <https://code.google.com/p/imageoptim/issues/detail?can=2&start=0&num=100&q=&colspec=ID%20Type%20Status%20Priority%20Milestone%20Owner%20Summary%20Stars&groupby=&sort=&id=39>`__.
