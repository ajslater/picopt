# picopt

A multi-format, recursive, multiprocessor aware, command line lossless image optimizer utility that uses external tools to do the optimizing.

Picopt depends on Python [PIL](http://www.pythonware.com/products/pil/) to identify files and Python [rarfile](https://pypi.python.org/pypi/rarfile) to open CBRs.

Picopt drops hidden timestamps at the root of your image directories to avoid reoptimizing images picopt has already optimized.

The actual image optimization is accomplished by external programs.

## <a name="philosophy">Conversion Philosophy</a>

### Lossy Images

JPEG & WebP images are likely the best and most practical lossy image formats. Converting lossy images rarely makes sense and so picopt optimizes them in their current format.

### Lossless Images

Lossless WebP images are smaller than PNG, much smaller than GIF and, of course, a great deal smaller thein uncompressed bitmaps like BMP. As such the best practice is probably to convert all lossless images to WebP Lossless as now all major browsers support it. The only downside is that decoding WebP Lossless takes on average 50% more CPU than PNG.

### Sequenced Images

Sequenced Images, like animated GIFs and WebP, most of the time, should be converted to a compressed video format like HEVC or VP9. There are several situations where this is impractical and so Animated WebP is now a good substitute.

## <a name="programs">External Programs</a>

### JPEG

To optimize JPEG images. Picopt needs one of [mozjpeg](https://github.com/mozilla/mozjpeg) or [jpegtran](http://jpegclub.org/jpegtran/) on the path. in order of preference.

### PNG, PNM, GIF, BMP

To optimize lossless images like PNG, PNM, GIF, and BMP, picopt requires either [optipng](http://optipng.sourceforge.net/) or [pngout](http://advsys.net/ken/utils.htm) be on the path. Optipng provides the most advantage, but best results will be had by using pngout as well.

### Animated GIF

Animated GIFs are optimized with [gifsicle](http://www.lcdf.org/gifsicle/) if it is available. Picopt nag you to convert your file to [HTML5 video](http://gfycat.com/about), but does not provide this service itself.

### WebP

WebP lossless & lossy formats are optimized with [cwebp](https://developers.google.com/speed/webp/docs/cwebp).

### EPub

EPub Books are zip files that often contain images.

### CBZ & CBR

Picopt uncompresses, optimizes and rezips [comic book archive files](https://en.wikipedia.org/wiki/Comic_book_archive). Be aware that CBR rar archives will be rezipped into CBZs instead of CBR. Comic book archive optimization is not turned on by default to prevent surprises.

## <a name="install">Install</a>

### System Dependencies

picopt requires several external system dependencies to run. We must install these first

#### macOS

    brew install webp mozjpeg optipng jonof/kenutils/pngout gifsicle

ln -s $(brew --prefix)/opt/mozjpeg/bin/jpegtran /usr/local/bin/mozjpeg

Unfortunately hombrew's `webp` formula does not yet install the gif2webp tool that picopt uses for converting animated gifs to animated webps.
You may manually download it and put it in your path at [Google's WebP developer website](https://developers.google.com/speed/webp/download)

#### Debian / Ubuntu

    apt-get install optipng gifsicle python-imaging webp

if you don't want to install mozjpeg using the instructions below then use jpegtran:

    apt-get install libjpeg-progs

#### Redhat / Fedora

    yum install optipng gifsicle python-imaging libwebp-tools

if you don't want to install mozjpeg using the instructions below then use jpegtran:

    yum install libjpeg-progs

#### MozJPEG

mozjpeg offers better compression than libjpeg-progs jpegtran. It may or
may not be packaged for your \*nix, but even when it is, picopt requires that its separately compiled version of jpegtran be symlinked to 'mozjpeg' somewhere in the path.

Instructions for installing on macOS are given above, but most Linux distributions still require a more manual install as elucidated here on [Casey Hoffer's blog](https://www.caseyhofford.com/2019/05/01/improved-image-compression-install-mozjpeg-on-ubuntu-server/)

#### pngout

pngout is a useful compression to use after optipng. It is not packaged for linux, but you may find the latest binary version [on JonoF's site](http://www.jonof.id.au/kenutils). Picopt looks for the binary to be called `pngout`

### Picopt python package

    pip install picopt

## <a name="usage">Usage</a>

Optimize all JPEG files in a directory:

    picopt *.jpg

Optimize all files and recurse directories:

    picopt -r *

Optimize files and recurse directories AND optimize comic book archives:

    picopt -rc *

Optimize files, but not lossless files:

    picopt -OPG *

Optimize files, but not jpegs:

    picopt -JT *

Optimize files, but not animated gifs:

    picopt -G *

Just list files picopt.py would try to optimize:

    picopt -l *

Optimize everything in my iPhoto library, but only after the last time i did this, skipping symlinks to avoid massive amounts of duplicate work. Don't convert lossless files to PNGs because that would confuse iPhoto. Also drop a timestamp file so I don't have to remember the last time I did this:

    picopt -rSYt -D '2013 June 1 14:00' 'Pictures/iPhoto Library'

## <a name="package">Packages</a>

- [PyPI](https://pypi.python.org/pypi/picopt/)
- [Arch Linux](https://aur.archlinux.org/packages/picopt/)

## <a name="alternatives">Alternatives</a>

[imagemin](https://github.com/imagemin/imagemin-cli) looks to be an all in one cli and gui solution with bundled libraries, so no awkward dependencies.
[Imageoptim](http://imageoptim.com/) is an all-in-one OS X GUI image optimizer. Imageoptim command line usage is possible with [an external program](https://code.google.com/p/imageoptim/issues/detail?can=2&start=0&num=100&q=&colspec=ID%20Type%20Status%20Priority%20Milestone%20Owner%20Summary%20Stars&groupby=&sort=&id=39).
