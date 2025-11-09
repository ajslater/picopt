# 📰 Picopt News

## v5.3

- Use webpmux if available to unpack and repack animated webp images.
- Fix Animated WebP images:
    - Sometimes being repacked in reverse frame order.
    - Sometimes degrading quality.
    - Sometimes dropping frames.
- Use secure python temporary directory for unpacking animated webp images and
  chaining webp conversion input.
- Use img2webp if available for animated conversion to webp from png.
- Use memory buffers instead of disk for webp output.

## v5.2.2

- Support Python 3.14

## v5.2.1

- The confuse library dependency doesn't support Python 3.14. So neither does
  picopt :(

## v5.2.0

- MozJpeg is now an internal python module. External mozjpeg & jpegtran support
  removed.

## v5.1.1

- Fix verbosity default too high.

## v5.1.0

- Use gif2webp to convert GIFs to WebP. It saves space compared to picopt's
  custom method.

## v5.0.1

- Fix crash converting animated images with bad duration metadata.

## v5.0.0

- Alert!
    - Timestamps options changed, invalidating old timestamps. On your first run
      in a path with picopt 5.0 you may use the `-N` option to ignore the old
      timestamp's config differences.
- Fixes
    - Fix tif & animated gifs were not converted to pngs when specified.
    - Fix --ignore option wildcards and performance.
    - --ignore is now case insensitive on case insenstitive filesystems
- Features
    - Picopt learned to optimize 7-Zip and Tar Archives.
    - Ignore dotfiles by default. Disable with -I.
    - -T --test option becomes -d --dry-run
    - colors changed.
- Performance
    - Archives skipped without unpacking contents if all contents are skippable.
    - Animated pngs better optimized with oxipng
    - Faster scanning for legacy timestamps on startup.
- Dev
    - Updated treestamps
    - uv build system

## v4.0.4

- Pillow 11 support.
- Better jpeg xmp preservation.
- Fix crash on reporting some errors.
- README Redhat installation and spelling fixes by @bpepple

## v4.0.3 - Bad release

## v4.0.2

- Fix windows mmap crash. Thanks @Fletcher.

## v4.0.1

- Reduce overzealous png optimization. Provide an option to do that.

## v4.0.0

- Alert!
    - Timestamps options changed, invalidating old timestamps. On your first run
      in a path with picopt 4.0 use the `-N` option to ignoring the old
      timestamp.
- Features
    - Support optimizing SVG with svgo.
    - Support converting more lossless formats to PNG & WEBP: CUR, DIB, FITS,
      IMT, PCX, PIXAR, PSD, QOI, SGI, SPIDER, SUN, TGA, XBM, XPM.
    - Support converting animated formats to animated PNG.
    - Support converting losslessly converting MPO to JPEG (choose primary
      image)
    - Internal oxipng replaces external optipng for png compression.
    - Better support for preserving EXIF, ICC_PROFILE, & XMP data across
      optimization and conversion.
    - `--destroy-metadata` option becomes `--strip-metadata`
    - `--near-lossless` option for lossless WebP.
    - `--preserve` file attributes after optimization.
    - `--disable-programs` option.
    - ~25% faster due to avoiding disk io.
- Fixes
    - wal file would write illegal key names and fail to load for some files.
- Dev
    - walk.run now returns totals instead of running report on them.

## v3.3.7

- Fix
    - Remove Lossy WebP optimization. Wasn't optimal.
    - Fix non zero exit code on success.
- Features
    - Improve WebP optimization.

## v3.3.6

- If unrar is not available do not convert rar. Was making empty zips.
- Support zip deflate64

## v3.3.5

- Wasn't skipping directories appropriately.

## v3.3.4

- Keep original path suffix if not converting.

## v3.3.3

- Update treestamps fixes bugs.

## v3.3.2

- Upstream treestamps returns to relative stamp paths for portability.

## v3.3.1

- Upstream treestamps fixes crashes and check_config option.

## v3.3.0

- Update deps including treestamps.
- New option to disable treestamps check of config section for a run.

## v3.2.6

- Fix cleanup of temp dir when repacking a container or animated images fails.
- Simple error message instead of stack trace on config failure.

## v3.2.5

- Fix occasionally removing both final and originals on case insensitive
  filesystem.

## v3.2.4

- Fix error reporting
- Fix WebP Lossless detection

## v3.2.3

- Color help. Change bigger color to blue.

## v3.2.2

- Remove more debug print statements.

## v3.2.1

- Remove debug print statements.

## v3.2.0

- Animated PNG conversion to WEBP support
- Fixed showing total saved at the end
- Highlight conversions with color output
- Lowlight nothing saved results with dark colors
- Suppress stdout from programs
- Report errors in more detail
- Fixed verbosity count for cli
- Report on unhandled formats at verbosity > 1.

## v3.1.4

- Remove extraneous debug print statement.

## v3.1.3

- Fix not deleting working files
- Add progress dots to verbose level 1

## v3.1.2

- Fix treestamps factory breaking.

## v3.1.1

- Fix not skipping older than timestamp files.
- Add verbose logging skip files reason.

## v3.1.0

- Change walk algorithm to complete directories and containers before opening
  new ones.
- Case insensitive format config.
- Ignore symlinks when asked to in timestamps.

## v3.0.5

- Timestamps respect ignore option.
- Don't record timestamps for items inside containers.
- Traverse directories alphabetically.

## v3.0.4

- Fix timestamps not recording sometimes.

## v3.0.3

- Don't dump full timestamps after every dir completes.

## v3.0.2

- Trap container repack errors.

## v3.0.1

- Update treestamps to accept string paths.

## v3.0.0

- Formats
    - WebP lossless, lossy and animated support.
    - Gain support for .zip archives
    - EPub support. ePub contents are never converted.
    - TIFF support
- Timestamps
    - Timestamps are now kept in .picopt_treestamps.yaml files.
    - Picopt will convert and clean up old style timestamps.
    - Timestamps are now recorded after optimizing every image for each image
      individually instead of directories, preserving progress.
    - Timestamps record configuration. Running with a new config invalidates
      non-matching timestamps.
- Configuration
    - .picoptrc.yaml files can configure options
    - Changed cli option names.
    - Removed cli args for manually disabling programs
    - Faster checking for external programs
- Fall back to Pillow optimization if better external programs not found.
- Colored terminal output.
- Fixes
    - Cleans up old temporary files from aborted picopt runs.
    - Fix condition where new files in an old archive were not processed.
    - optiping optimization level changed to o5
    - Exif & icc metadata preserved in all formats much better by default.

## v2.2.1

- Support python v3.9
- Preserve comments when optimizing comic archives

## v2.2.0

- Walk in alphabetical order
- Check code with vulture and radon

## v2.1.0

- Remove adv support.
- Remove jpegrescan support. Inferior to mozjpeg
- Don't preserve ctime/mtime when making new pngs
- Use pytest instead of nosetest
- Require formatting with black & isort

## v2.0.1

- Pillow 7 compatibility

## v2.0.0

- Stop supporting python 2
- Switch to poetry build system
- Type checking with mypy

## v1.6.3

- Don't use pngout on 16 bit pngs because it crashes
- Fix broken option -D --optimize_after

## v1.6.2

- Fix illegal stack trace call.

## v1.6.1

- Fix exception handling when extern process returns non-zero

## v1.6.0

- Report on all errors at the end
- Remove PIL support in favor of Pillow.
- Python3 proof

## v1.5.3

- Fix hang on external program error. Likely with 16 bit PNGs and pngout.

## v1.5.2

- More compatibility with Python 3
- Fix formats as a list when it should be a set issue

## v1.5.1

- Drop TIFF support.
- Fix space savings reporting bug where savings always equaled zero

## v1.4.5

- When setting new timestamps, don't remove timestamps above the root paths
  specified as input

## v1.4.4

- Use timestamp caching more often

## v1.4.3

- Fix bug where files were not detected
- Fix broken timestamp processing.

## v1.4.1

- fix main entry bug for cli

## v1.4.0

- let the archive date override the newness of its contained files.
- let the cli run programmatically with passed in args
- code no longer relies on cwd for finding its way
- -d --directory argument goes away
- nosetests now run the old inadequate cli tests
- big code cleanup
- don't redetect new image format type

## v1.3.3

- Print found picopt timestamps
- Lots of linting
- Fix jpeg_multithread flag
- moved tests out of picopt module

## v1.3.2

- Keep **version** in one place in picopt/**init**.py

## v1.3.1

- Remove dev dependencies from installed requirements.

## v1.3

- break up monolithic picopt into modules. No functional change.

## v1.2

- picopt learned the -j option for specifying number of subprocesses (thanks
  @DarwinAwardWinner)

## v1.1.3

- fixed rare crash on sequential gif detection

## v1.1.2

- detect PNM images properly for conversion with optipng

## v1.1.1

- fix verifying gif crash (thanks @DarwinAwardWinner)

## v1.1.0

- mozjpeg support (thanks to @crass00)

## v1.0.6

- Fix disabled comic archive switch.

## v1.0.5

- Fix timestamp writing to happen once workers have finished
- Fix size saved if size in is zero

## v1.0.3

- Fix -v to actually be more verbose than default
- Fix from Dennis Schwertel to jpegtran runner

## v1.0.2

- Fix -Y to actually disable not enable type conversion

## v1.0.1

- Fix typos in --help

## v1.0.0

- Packaging for PyPI
- Internal changes to make picopt more modular and library friendly
- CHANGED COMMAND LINE ARGUMENT LETTERS.
- Added verbosity setting
- Truncated relative and in-archive path names for readibiliy
- Nag about animated gifs less

## v0.12.0.1

- Fix error on no directories

## v0.12.0

- Added multithreaded jpegrescan operation when picopt isn't using up all the
  cores at the suggestion of Alex Roe.
- Added destroy metadata option at the suggestion of Alex Roe.

## v0.11.4

- Added to ArchLinux by Alex Roe.
