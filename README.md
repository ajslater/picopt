# picopt

A multi-format, recursive, multiprocessor aware, command line lossless image optimizer utility that uses external tools to do the optimizing.

Picopt depends on Python [PIL](http://www.pythonware.com/products/pil/) to identify files and Python [rarfile](https://pypi.python.org/pypi/rarfile) to open CBRs.

Picopt will optionally drop hidden timestamps at the root of your image directories to avoid reoptimizing images picopt has already optimized.

The actual image optimization is best accomplished by external programs.

## <a name="philosophy">Conversion Philosophy</a>

### Lossy Images

JPEG & Lossy WebP images are likely the best and most practical lossy image formats. Converting lossy images rarely makes sense and so picopt only optimizes them in their current format.

### Lossless Images

Lossless WebP images are smaller than PNG, much smaller than GIF and, of course, a great deal smaller thein uncompressed bitmaps like BMP. As such the best practice is probably to convert all lossless images to WebP Lossless as now all major browsers support it. The only downside is that decoding WebP Lossless takes on average 50% more CPU than PNG.

### Sequenced Images

Sequenced Images, like animated GIFs and WebP, most of the time, should be converted to a compressed video format like HEVC or VP9. There are several situations where this is impractical and so Animated WebP is now a good substitute.

### Conversion

By default picopt does not convert images between formats. You must turn on conversion to PNG or WebP explicitly.

## <a name="formats">Formats</a>

- By default picopt will optimize GIF, JPEG, PNG and WEBP images.
- Picopt can optionally optimize ZIP, ePub, and CBZ containers.
- Picopt can be told to convert lossless images such as BPM, PPM, GIF, TIFF into PNG, and all of the mentioned lossless formats into WebP.
- Picopt can convert Animated GIFs into Animated WebP files.
- Picopt can convert Animated PNGs (APNG) into Animated WebP files, but does not optimize APNG as APNG.
- Picopt can convert RAR files into Zipfiles and CBR files into CBZ files.

## <a name="programs">External Programs</a>

Picopt will perform some minor optimization on most formats natively without using external programs, but this is not very good compared to the optimizations external programs can provide.

### JPEG

To optimize JPEG images. Picopt needs one of [mozjpeg](https://github.com/mozilla/mozjpeg) or [jpegtran](http://jpegclub.org/jpegtran/) on the path. in order of preference.

### PNG

To optimize PNG images or convert other lossless formats to PNG picopt requires either [optipng](http://optipng.sourceforge.net/) or [pngout](http://advsys.net/ken/utils.htm) be on the path. Optipng provides the most advantage, but best results will be had by using pngout as well.

### Animated GIF

Animated GIFs are optimized with [gifsicle](http://www.lcdf.org/gifsicle/) if it is available.

### WebP

WebP lossless & lossy formats are optimized with [cwebp](https://developers.google.com/speed/webp/docs/cwebp).

### EPub

EPub Books are zip files that often contain images and picopt unpacks and repacks this format natively. Images within the epub are handled by other programs. EPub optimization is not turned on by default.
EPub contents are never converted to other formats because it would break internal references to them.

### CBZ & CBR

Picopt uncompresses, optimizes and rezips [comic book archive files](https://en.wikipedia.org/wiki/Comic_book_archive). Be aware that CBR rar archives may only be rezipped into CBZs instead of CBR. Comic book archive optimization is not turned on by default to prevent surprises.

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

Instructions for installing on macOS are given above.
Some near recent binaries for Windows and Debian x86 [can be found here](https://mozjpeg.codelove.de/binaries.html).
Most Linux distributions still require a more manual install as elucidated here on [Casey Hoffer's blog](https://www.caseyhofford.com/2019/05/01/improved-image-compression-install-mozjpeg-on-ubuntu-server/)

#### pngout

pngout is a useful compression to use after optipng. It is not packaged for linux, but you may find the latest binary version [on JonoF's site](http://www.jonof.id.au/kenutils). Picopt looks for the binary to be called `pngout`

### Picopt python package

    pip install picopt

## <a name="usage">Usage Examples</a>

Optimize all JPEG files in a directory:

    picopt *.jpg

Optimize all files and recurse directories:

    picopt -r *

Optimize files, recurse directories, also optimize ePub & CBZ containers, convert lossless images into WEBP, convert CBR into CBZ.

    picopt -rx EPUB,CBR,CBZ -c WEBP,CBZ *

Optimize files and recurse directories AND optimize comic book archives:

    picopt -rx CBZ *

Optimize comic directory recursively. Convert CBRs to CBZ. Convert lossless images, including TIFF, to lossless WEBP. Do not follow symlinks. Set timestamps.

    picopt -rStc CBZ,WEBP -x TIFF,CBR,CBZ /Volumes/Media/Comics

Optimize all files, but only JPEG format files:

    picopt -f JPEG *

Optimize files and containers, but not JPEGS:

    picopt -f GIF,PNG,WEBP,ZIP,CBZ,EPUB *

Optimize files, but not animated gifs:

    picopt -f PNG,WEBP,ZIP,CBZ,EPUB *

Just list files picopt.py would try to optimize:

    picopt -L *

Optimize pictures in my iPhoto library, but only after the last time I did this, skipping symlinks to avoid duplicate work. Also drop a timestamp file so I don't have to remember the last time I did this:

    picopt -rSt -D '2013 June 1 14:00' 'Pictures/iPhoto Library'

## <a name="package">Packages</a>

- [PyPI](https://pypi.python.org/pypi/picopt/)
- [Arch Linux](https://aur.archlinux.org/packages/picopt/)

## <a name="alternatives">Alternatives</a>

[imagemin](https://github.com/imagemin/imagemin-cli) looks to be an all in one cli and gui solution with bundled libraries, so no awkward dependencies.
[Imageoptim](http://imageoptim.com/) is an all-in-one OS X GUI image optimizer. Imageoptim command line usage is possible with [an external program](https://code.google.com/p/imageoptim/issues/detail?can=2&start=0&num=100&q=&colspec=ID%20Type%20Status%20Priority%20Milestone%20Owner%20Summary%20Stars&groupby=&sort=&id=39).
