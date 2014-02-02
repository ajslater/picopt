picopt
======

A multi-format, recursive, multiprocessor aware, command line image optimizer utility that uses external tools to do the optimizing.

Picopt depends on Python [PIL](http://www.pythonware.com/products/pil/) to identify files and [rarfile](https://pypi.python.org/pypi/rarfile) to open CBRs.

To optimize JPEG images. Picopt needs either [jpegrescan](https://github.com/kud/jpegrescan) or [jpegtran](http://jpegclub.org/jpegtran/) on the path. jpegrescan is preferred.

To optimize lossless images like PNG, PNM, GIF, TIFF and BMP, picopt requires either [optipng](http://optipng.sourceforge.net/), [advpng](http://advancemame.sourceforge.net/doc-advpng.html) or [pngout](http://advsys.net/ken/utils.htm) be on the path. optipng provides the most advantage, but best results are acheived by using both utilities. advpng support is disabled by default and must be explicitly enabled on the command line.

Animated GIFs are optimized with [gifsicle](http://www.lcdf.org/gifsicle/) if it is available.

Picopt uncompresses, optimizes and rezips [comic book archive files](https://en.wikipedia.org/wiki/Comic_book_archive). Be aware that CBR rar archives will be rezipped into CBZs instead of CBR.

Picopt allows you to drop picopt timestamps at the root of your recursive optimization trees so you don't have to remember which files to optimize or when you last optimized.

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

### Dependancies
#### Debian / Ubuntu
    apt-get install python-imaging

### Picopt
    pip install picopt

Usage
-----
Optimize files:

    picopt *.jpg

Optimize files and recurse directories:

    picotpt -r *

Optimize files and recurse directories AND optimize comic book archives:

    picopt -rc *

Optimize files, but not lossless files:

    picopt -op *

Optimize files, but not jpegs:

    picopt -jt *

Optimize files, but not animated gifs:

    picopt -g *

Just list files picopt.py would try to optimize:

    picopt -l *

Optimize everything in my iPhoto library, but only after the last time i did this, skipping symlinks to avoid massive amounts of duplicate work. Don't convert lossless files to PNGs because that would confuse iPhoto. Also drop a timestamp file so I don't have to remeber the last time I did this:

    picopt -rSCT -D '2013 June 1 14:00' 'Pictures/iPhoto Library'

Packaged For
------------

* [PyPI](https://pypi.python.org/pypi/picopt/0.13.1)
* [Arch Linux](https://aur.archlinux.org/packages/picopt/)


Alternatives
------------

[imageoptim](http://imageoptim.com/) is an OS X GUI optimizer. It integrates the various optimization programs so you don't have to install them separately. It does not handle comic book archives. Its drag'n'drop UI is pretty nice. It also has AdvPNG support which I've disabled in picopt because I've never seen it provide any advantage. Command line usage is possible with [an external program](https://code.google.com/p/imageoptim/issues/detail?can=2&start=0&num=100&q=&colspec=ID%20Type%20Status%20Priority%20Milestone%20Owner%20Summary%20Stars&groupby=&sort=&id=39).
