# picopt

A multi-format, recursive, multiprocessor aware, command line, lossless image optimizer utility that can use external tools for even better optimizing.

Picopt will optionally drop hidden timestamps at the root of your image directories to avoid reoptimizing images picopt has already optimized.

## 💭 <a name="philosophy">Conversion Philosophy</a>

### Warning

Picopt transforms images in place and throws out the old image. Always have a backup of images before running picopt in case you are not satisfied with the results.

### Lossy Images

Converting lossy images rarely makes sense and so picopt only optimizes them in their current format.

- JPEG images are optimized with MozJpeg's jpegtran.
- WEBP Lossy images are not optimized. There is no current way to preserve information without running it through a lossy process again.

### Lossless Images

Lossless WebP images are smaller than PNG, much smaller than GIF and, of course, a great deal smaller thein uncompressed bitmaps like BMP. As such the best practice is probably to convert all lossless images to WebP Lossless as now all major browsers support it. The only downside is that decoding WebP Lossless takes on average 50% more CPU than PNG.
All major desktop and mobile browsers support WEBP. WEBP is the lossless format of choice. Until perhaps JPEG XL support arrives for browsers.

### Sequenced Images

Sequenced Images, like animated GIFs and WebP, most of the time, should be converted to a compressed video format like HEVC, VVC, VP9 or VP10. There are several situations where this is impractical and so Animated WebP is now a good substitute.

### Conversion

By default picopt does not convert images between formats. You must turn on conversion to PNG or WebP explicitly.

## 🖼️ <a name="formats">Formats</a>

- By default picopt will optimize GIF, JPEG, PNG, SVG and WEBP images.
- Picopt can optionally optimize ZIP, ePub, and CBZ containers.
- Picopt can convert many lossless images such as BMP, CBR, CUR, DIB, FITS, GIF, IMT, PCX, PIXAR, PNG,
  PPM, PSD, QOI, SGI, SPIDER, SUN, TGA, TIFF, XBM, and XPM into PNG and WEBP.
- Picopt can convert Animated GIF, TIFF, and FLI into Animated PNG or WebP files.
- Picopt can convert Animated GIF, TIFF, FLI, and PNG into Animated WebP files.
- Picopt can convert RAR files into Zipfiles and CBR files into CBZ files.

Because picopt supports so many lossless image formats, to avoid surprises if you specify a conversion target, picopt will only convert GIF and PNG images to the target by default. To convert another format, like BMP, to WEBP you must specify that you want to read the BMP format _and_ that you want to convert it to WEBP:

```sh
picopt -x BMP -c WEBP big_old.bmp
```

### JPEG

To optimize JPEG images at all picopt needs one of [mozjpeg](https://github.com/mozilla/mozjpeg) or [jpegtran](http://jpegclub.org/jpegtran/) on the path. in order of preference.

### PNG

To optimize PNG images or convert other lossless formats to PNG picopt requires either [oxipng](https://github.com/shssoichiro/oxipng), [optipng](https://optipng.sourceforge.net/), or [pngout](http://advsys.net/ken/utils.htm) be on the path. oxipng provides the most advantage, but best results will be had by using pngout as well.

### Animated GIF

Animated GIFs are optimized with [gifsicle](http://www.lcdf.org/gifsicle/) if it is available.

### WebP

WebP lossless formats are optimized with [cwebp](https://developers.google.com/speed/webp/docs/cwebp).

### SVG

Picopt can only optimize SVGs if [svgo](https://github.com/svg/svgo) is on the path.

### EPub

EPub Books are zip files that often contain images and picopt unpacks and repacks this format natively. Images within the epub are handled by other programs. EPub optimization is not turned on by default.
EPub contents are never converted to other formats because it would break internal references to them.

### CBZ & CBR

Picopt uncompresses, optimizes and rezips [comic book archive files](https://en.wikipedia.org/wiki/Comic_book_archive). Be aware that CBR rar archives may only be rezipped into CBZs instead of CBR. Comic book archive optimization is not turned on by default to prevent surprises.

## 📦 <a name="install">Install</a>

### System Dependencies

picopt is most effective with ependencies to run. We must install these first

#### macOS

```sh
brew install gifsicle mozjpeg oxipng svgo webp

ln -s $(brew --prefix)/opt/mozjpeg/bin/jpegtran /usr/local/bin/mozjpeg
```

#### Debian / Ubuntu

```sh
apt-get install gifsicle python-imaging webp
```

if you don't want to install mozjpeg using the instructions below then use jpegtran:

```sh
apt-get install libjpeg-progs
```

See mozjepg, oxipng, pngout & svgo install instructions below

#### Redhat / Fedora

```sh
yum install gifsicle oxipng python-imaging libwebp-tools
```

if you don't want to install mozjpeg using the instructions below then use jpegtran:

```sh
yum install libjpeg-progs
```

See mozjepg, pngout & svgo install instructions below

### Picopt python package

```sh
pip install picopt
```

## ⚙️ <a name="programs">External Programs</a>

Picopt will perform optimization on most lossless formats without using external programs, but much more compression is possible if these external programs are on your path.

#### mozjpeg

mozjpeg offers better compression than libjpeg-progs jpegtran. It may or
may not be packaged for your \*nix, but even when it is, picopt requires that its separately compiled version of jpegtran be symlinked to 'mozjpeg' somewhere in the path.

Instructions for installing on macOS are given above.
Some near recent binaries for Windows and Debian x86 [can be found here](https://mozjpeg.codelove.de/binaries.html).
Most Linux distributions still require a more manual install as elucidated here on [Casey Hoffer's blog](https://www.caseyhofford.com/2019/05/01/improved-image-compression-install-mozjpeg-on-ubuntu-server/)

#### oxipng

oxipng is a newer, maintained fork of optipng. Unfortunately it isn't packaged for many Linuxes, but it has easily downloaded binary installs at the [Github Oxipng Release Page](https://github.com/shssoichiro/oxipng/releases)

### optipng

optipng is frequently packaged and you may install it with homebrew, apt-get or yum. oxipng tends to give better results.

#### pngout

pngout is a compression tool that can be used by itself or for small extra compression after running oxipng or optipng. It does not run on 16 bit PNGs.

It can be installed on macOS with:

```sh
brew install jonof/kenutils/pngout
```

It is not packaged for linux, but you may find the latest binary version [on JonoF's site](http://www.jonof.id.au/kenutils). Picopt looks for the binary to be called `pngout`

#### svgo

svgo compresses SVGs. Svgo is packaged for homebrew, but picopt can also use it if it's installed with npm.

##### On Linux

To install svgo on Linux you can use the snap tool:

```sh
snap install svgo
```

Or you can install svgo with npm:

```sh
npm install -G svgo
```

## ⌨️ <a name="usage">Usage Examples</a>

Optimize all JPEG files in a directory:

```sh
picopt *.jpg
```

Optimize all files and recurse directories:

```sh
picopt -r *
```

Optimize files, recurse directories, also optimize ePub & CBZ containers, convert lossless images into WEBP, convert CBR into CBZ.

```sh
picopt -rx EPUB,CBR,CBZ -c WEBP,CBZ *
```

Optimize files and recurse directories AND optimize comic book archives:

```sh
picopt -rx CBZ *
```

Optimize comic directory recursively. Convert CBRs to CBZ. Convert lossless images, including TIFF, to lossless WEBP. Do not follow symlinks. Set timestamps.

```sh
picopt -rStc CBZ,WEBP -x TIFF,CBR,CBZ /Volumes/Media/Comics
```

Optimize all files, but only JPEG format files:

```sh
picopt -f JPEG *
```

Optimize files and containers, but not JPEGS:

```sh
picopt -f GIF,PNG,WEBP,ZIP,CBZ,EPUB *
```

Optimize files, but not animated gifs:

```sh
picopt -f PNG,WEBP,ZIP,CBZ,EPUB *
```

Just list files picopt.py would try to optimize:

```sh
picopt -L *
```

Optimize pictures in my iPhoto library, but only after the last time I did this, skipping symlinks to avoid duplicate work. Also drop a timestamp file so I don't have to remember the last time I did this:

```sh
picopt -rSt -D '2013 June 1 14:00' 'Pictures/iPhoto Library'
```

## 📦 <a name="package">Packages</a>

- [PyPI](https://pypi.python.org/pypi/picopt/)
- [Arch Linux](https://aur.archlinux.org/packages/picopt/)

## 👀 <a name="alternatives">Alternatives</a>

- [imagemin](https://github.com/imagemin/imagemin-cli) looks to be an all in one cli and gui solution with bundled libraries, so no awkward dependencies.

- [Imageoptim](http://imageoptim.com/) is an all-in-one OS X GUI image optimizer. Imageoptim command line usage is possible with [an external program](https://code.google.com/p/imageoptim/issues/detail?can=2&start=0&num=100&q=&colspec=ID%20Type%20Status%20Priority%20Milestone%20Owner%20Summary%20Stars&groupby=&sort=&id=39).
