# Picopt

A multi-format, recursive, multiprocessor aware, command line, lossless image
optimizer utility that can use external tools for even better optimizing.

Picopt will optionally drop hidden timestamps at the root of your image
directories to avoid reoptimizing images picopt has already optimized.

## 📰 News

Picopt has a [NEWS file](NEWS.md) for changes that might be of interest to
users.

## 🕸️ HTML Docs

[HTML formatted docs are available here](https://picopt.readthedocs.io)

## 💭 Conversion Philosophy

### Warning

Picopt transforms images in place and throws out the old image. Always have a
backup of images before running picopt in case you are not satisfied with the
results.

### Lossy Images

Converting lossy images rarely makes sense and so picopt only optimizes them in
their current format.

- JPEG images are optimized with MozJpeg's jpegtran.
- WEBP Lossy images are not optimized. There is no current way to preserve
  information without running it through a lossy process again.

### Lossless Images

Lossless WebP images are smaller than PNG, much smaller than GIF and, of course,
a great deal smaller than uncompressed bitmaps like BMP. As such the best
practice is probably to convert all lossless images to WebP Lossless as now all
major browsers support it. The only downside is that decoding WebP Lossless
takes on average 50% more CPU than PNG. All major desktop and mobile browsers
support WEBP. WEBP is the lossless format of choice. Until perhaps JPEG XL
support arrives for browsers.

### Sequenced Images

Sequenced Images, like animated GIFs and WebP, most of the time, should be
converted to a compressed video format like HEVC, VVC, VP9 or VP10. There are
several situations where this is impractical and so Animated WebP is now a good
substitute.

### Conversion

By default, picopt does not convert images between formats. You must turn on
conversion to PNG or WebP explicitly.

## 🖼️ Formats

- By default picopt will optimize GIF, JPEG, PNG, and WEBP images.
- Picopt can optionally optimize SVG images, ZIP, ePub, and CBZ containers.
- Picopt can convert many lossless images such as BMP, CBR, CUR, DIB, FITS, GIF,
  IMT, PCX, PIXAR, PNG, PPM, PSD, QOI, SGI, SPIDER, SUN, TGA, TIFF, XBM, and XPM
  into PNG and WEBP.
- Picopt can convert Animated GIF, TIFF, and FLI into Animated PNG or WebP
  files.
- Picopt can convert Animated GIF, TIFF, FLI, and PNG into Animated WebP files.
- Picopt can convert MPO to JPEG by stripping secondary images (often thumbnails
  created by cameras) if a primary image exists. (Experimental).
- Picopt can convert RAR files into Zipfiles and CBR files into CBZ files.

Because picopt supports so many lossless image formats, to avoid surprises if
you specify a conversion target, picopt will only convert GIF and PNG images to
the target by default. To convert another format, like BMP, to WEBP you must
specify that you want to read the BMP format _and_ that you want to convert it
to WEBP:

<!-- eslint-skip -->

```sh
picopt -x BMP -c WEBP big_old.bmp
```

### JPEG

Picopt uses an internal mozjpeg python module to optimize JPEG images.

### PNG & APNG

Picopt uses an internal oxipng python module to optimize PNG images and convert
other lossless formats to PNG picopt. The external
[pngout](http://advsys.net/ken/utils.htm) tool can provide a small extra bit of
compression.

Animated PNGs are optimized with the internal optimizer.

### Animated GIF

Gifs and Animated GIFs are optimized with
[gifsicle](http://www.lcdf.org/gifsicle/) if available. or interaallly if is
not. Gifsicle only provides a small advantage over the internal optimizer.

### WebP

WebP lossless formats are optimized with
[cwebp](https://developers.google.com/speed/webp/docs/cwebp) if available and
with the internal optimizer if not. cwebp provides significant improvements over
the internal optimizer.

When configured to convert GIFS to WebP, Animated GIFs are converted to WebP
with the [gif2webp](https://developers.google.com/speed/webp/docs/gif2webp)
binary if it exists. It is normally distributed as part of the webp package.

#### Experimental option

This experimental options is activated with an environment variable.

Set `PICOPT_ENABLE_IMG2WEBP=1` to make picopt optimize animated WebPs and
convert animated PNGs to webp with the
[img2webp](https://developers.google.com/speed/webp/docs/img2webp) binary. In my
experiments img2webp has performed worse than picopt's custom algorithm using
PIL & cwebp

### SVG

Picopt can only optimize SVGs if [svgo](https://github.com/svg/svgo) is on the
path.

### MPO (Experimental)

Picopt can extract the primary image from a multi JPEG MPO that also contains
thumbnails and convert the file to an ordinary JPEG. Picopt will also optimize
this image if it can. To enable this you must run with `-x MPO -c JPEG`
Steroscopic MPOs should have no primary image tagged in the MPO directory and be
unaffected.

This feature has not been tested with a large variety of MPOs and should be
considered experimental.

### EPub

EPub Books are zip files that often contain images and picopt unpacks and
repacks this format natively. Images within the epub are handled by other
programs. EPub optimization is not turned on by default. EPub contents are never
converted to other formats because it would break internal references to them.

### CBZ & CBR

Picopt uncompresses, optimizes and rezips
[comic book archive files](https://en.wikipedia.org/wiki/Comic_book_archive). Be
aware that CBR rar archives may only be rezipped into CBZs instead of CBR. Comic
book archive optimization is not turned on by default to prevent surprises.

## 📦 Install

### System Dependencies

#### Python

Picopt requires Python 3.10 or greater installed on whichever system you use.

Picopt is most effective with these binary dependencies installed. We must
install these first

#### macOS

<!-- eslint-skip -->

```sh
brew install gifsicle mozjpeg svgo webp

ln -s $(brew --prefix)/opt/mozjpeg/bin/jpegtran /usr/local/bin/mozjpeg
```

#### Debian / Ubuntu, Windows Linux Subsystem

<!-- eslint-skip -->

```sh
apt-get install gifsicle python-imaging webp
```

if you don't want to install mozjpeg using the instructions below then use
jpegtran:

<!-- eslint-skip -->

```sh
apt-get install libjpeg-progs
```

See mozjepg, pngout & svgo install instructions below

#### Redhat / Fedora

<!-- eslint-skip -->

```sh
dnf install gifsicle python3-pillow libwebp-tools
```

if you don't want to install mozjpeg using the instructions below then use
jpegtran:

<!-- eslint-skip -->

```sh
dnf install libjpeg-turbo-utils
```

See mozjepg, pngout & svgo install instructions below

### Picopt python package

<!-- eslint-skip -->

```sh
pip install picopt
```

## ⚙️ <a name="programs">External Programs</a>

Picopt will perform optimization on most lossless formats without using external
programs, but much more compression is possible if these external programs are
on your path.

### pngout

pngout is a compression tool that can be used for small extra compression. It
does not run on 16 bit PNGs.

It can be installed on macOS with:

<!-- eslint-skip -->

```sh
brew install jonof/kenutils/pngout
```

It is not packaged for linux, but you may find the latest binary version
[on JonoF's site](http://www.jonof.id.au/kenutils). Picopt looks for the binary
to be called `pngout`

### svgo

svgo compresses SVGs. Svgo is packaged for homebrew, but picopt can also use it
if it's installed with npm.

#### On Linux

To install svgo on Linux you can use the snap tool:

<!-- eslint-skip -->

```sh
snap install svgo
```

Or you can install svgo with npm:

<!-- eslint-skip -->

```sh
npm install -G svgo
```

## ⌨️ Use Examples

Optimize all JPEG files in a directory:

<!-- eslint-skip -->

```sh
picopt *.jpg
```

Optimize all files and recurse directories:

<!-- eslint-skip -->

```sh
picopt -r *
```

Optimize files, recurse directories, also optimize ePub & CBZ containers,
convert lossless images into WEBP, convert CBR into CBZ.

<!-- eslint-skip -->

```sh
picopt -rx EPUB,CBR,CBZ -c WEBP,CBZ *
```

Optimize files and recurse directories AND optimize comic book archives:

<!-- eslint-skip -->

```sh
picopt -rx CBZ *
```

Optimize comic directory recursively. Convert CBRs to CBZ. Convert lossless
images, including TIFF, to lossless WEBP. Do not follow symlinks. Set
timestamps.

<!-- eslint-skip -->

```sh
picopt -rStc CBZ,WEBP -x TIFF,CBR,CBZ /Volumes/Media/Comics
```

Optimize all files, but only JPEG format files:

<!-- eslint-skip -->

```sh
picopt -f JPEG *
```

Optimize files and containers, but not JPEGS:

<!-- eslint-skip -->

```sh
picopt -f GIF,PNG,WEBP,ZIP,CBZ,EPUB *
```

Optimize files, but not animated gifs:

<!-- eslint-skip -->

```sh
picopt -f PNG,WEBP,ZIP,CBZ,EPUB *
```

Just list files picopt.py would try to optimize:

<!-- eslint-skip -->

```sh
picopt -L *
```

Optimize pictures in my iPhoto library, but only after the last time I did this,
skipping symlinks to avoid duplicate work. Also drop a timestamp file so I don't
have to remember the last time I did this:

<!-- eslint-skip -->

```sh
picopt -rSt -D '2013 June 1 14:00' 'Pictures/iPhoto Library'
```

## 📦 Packages

- [PyPI](https://pypi.python.org/pypi/picopt/)
- [Arch Linux](https://aur.archlinux.org/packages/picopt/)

## 👀 Alternatives

- [imagemin](https://github.com/imagemin/imagemin-cli) looks to be an all in one
  cli and gui solution with bundled libraries, so no awkward dependencies.

- [Imageoptim](http://imageoptim.com/) is an all-in-one OS X GUI image
  optimizer. Imageoptim command line usage is possible with
  [an external program](https://code.google.com/p/imageoptim/issues/detail?can=2&start=0&num=100&q=&colspec=ID%20Type%20Status%20Priority%20Milestone%20Owner%20Summary%20Stars&groupby=&sort=&id=39).

## 🛠️ Development

Picopt code is hosted at [Github](https://github.com/ajslater/picopt)
