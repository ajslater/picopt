# 📰 Picopt News

## v6.11.0

### ✨ Added

- `-x MPO` optimizes every image in an MPO losslessly and keeps the file an MPO.
  iPhone photos are MPOs that carry an HDR gain map.
- A skipped image whose suffix names an enabled format it isn't, like an MPO
  named `.jpeg`, gets a warning that names the options that would take it.

### ♻️ Changed

- `-x MPO -c JPEG` keeps the first image of an MPO that tags no image as its
  primary, such as a stereoscopic MPO.
- `-D mozjpeg` skips JPEGs instead of passing them through unchanged.

### 🐛 Fixed

- `-x MPO -c JPEG` wrote JPEGs that still indexed the images it dropped, so some
  readers failed on them and picopt converted them again on every run. Running
  it again repairs those files.
- `-x MPO -c JPEG -D mozjpeg` no longer adds a second XMP block.
- Optimizing a JPEG no longer deletes the data appended after its image, like
  the gain map of an Android Ultra HDR photo or the video of a Google Motion
  Photo. An Ultra HDR photo's MP Index is rewritten to match, and a JPEG whose
  MP Index doesn't match its appended data is left unchanged.

### 🧑‍💻 Developer

- Remove piexif.

## v6.10.1

### 🧑‍💻 Developer

- Require oxipng-pybind 10.2.
- Require python-dateutil 3.0.

## v6.10.0

### ✨ Added

- `picopt doctor` takes run options and paths and checks that run: config
  errors, unknown config keys, where each option was set, the enabled formats it
  would skip, each path's `.picopt.yaml` files, and whether its timestamps would
  be kept. `picopt doctor -q` shows only problems.

### ♻️ Changed

- `picopt doctor` exits 1 only when a run with its options would fail or skip an
  enabled format, not whenever any tool is missing.

### 🐛 Fixed

- Converting to a `-c` format no longer also needs it in `-x`, e.g.
  `-x RAR -c ZIP`.
- Formats a broken install can't write are skipped instead of failing every
  file: JXL without pillow-jxl-plugin, WebP from a Pillow without libwebp,
  compressed tarballs from a Python without bz2 or lzma, and RAR from an unrar
  that can't extract RAR5.
- Animated WebP is optimized without webpmux instead of skipped.
- A broken rarfile, py7zr or pikepdf install now disables only its own formats,
  with a warning, instead of stopping every run.
- `dry_run` or `list_only` in a tree root's `.picopt.yaml` no longer turns off
  timestamps for that tree.

### 🧑‍💻 Developer

- Require packaging.

## v6.9.1

### 🐛 Fixed

- Some RAR and CBR archives no longer fail with "microsecond must be in
  0..999999".

## v6.9.0

### 💥 Breaking Changes

- Require Python 3.11.

### 🐛 Fixed

- Converting tar or 7z to zip or cbz, or repacking 7z or cb7, no longer turns
  directories into empty files that break extraction.
- Converted and repacked archives no longer make files rw-------. Tar and 7z
  permissions and 7z symlinks are kept; rar files get rw-r--r--.

### 🧑‍💻 Developer

- Update treestamps dependency to 5.1.1.
- Require py7zr 1.1.

## v6.8.2

### 🧑‍💻 Developer

- Update confuse dependency

## v6.8.1

### 🐛 Fixed

- A timestamps file discarded for a config mismatch is now rewritten by the run
  that discards it, even when that run optimizes nothing. Previously the
  rejected file survived unchanged and warned about the same mismatch on every
  subsequent run. Requires treestamps 5.0.1.

## v6.8.0

### ✨ Added

- Timestamps survive picopt upgrades that record new options. Only a changed
  option value invalidates them, so stamp files written before an option joined
  the recorded set stay valid at its default. Timestamps from before 6.7.0 work
  again.
- Timestamp files now open with a comment explaining what they are, that they
  are machine-written, and that deleting one just re-optimizes that tree.
- Discarding timestamps because a sub-directory `.picopt.yaml` changed now says
  so, instead of naming an internal key.
- README documents `.picopt_treestamps.yaml`: what it records, that it is never
  applied as configuration, and that it is safe to delete.

### ♻️ Changed

- Requires treestamps 5.0.0. Timestamp files no longer duplicate `ignore` and
  `symlinks` in a second block. Existing timestamp files still load, and
  upgrading invalidates nothing.

### 🐛 Fixed

- Config files are written atomically. A crash or full disk during `-w`, `-W`,
  or `--write-config-file` can no longer truncate a hand-written config.

## v6.7.0

### ✨ Added

- JPEG XL support, read and write, using the internal
  [pillow-jxl-plugin](https://github.com/Isotr0py/pillow-jpegxl-plugin) module.
- JXL is now optimized by default. `.jxl` files that previous versions ignored
  are re-encoded on a plain `picopt -r` run. Only lossless JXL is touched; lossy
  (XYB encoded) JXL is left alone, as lossy WebP is.
- Lossless images convert to JXL with `-c JXL`, which now leads the preference
  order for still images ahead of WEBP and PNG.
- New `--convert-jpeg-to-jxl` converts JPEG to JXL losslessly and reversibly:
  the JXL stores the original JPEG bitstream and can restore it byte for byte.
  Files carrying that reconstruction data are never re-encoded, so the original
  JPEG stays recoverable.
- New `--convert-webp-to-jxl` converts lossless WebP to JXL. Off by default
  because JXL support is still much thinner than WebP's.
- Both flags require `-c JXL` as well. JPEG and WEBP are formats picopt already
  processes by default, so unlike BMP or TIFF they cannot be gated by naming
  them with `-x`. A plain `-c JXL` still converts only GIF and PNG.

## v6.6.3

### 🐛 Fixed

- Corrupt images that PIL recognizes but cannot parse (e.g. a BMP with an
  unsupported pixel depth) are reported as a one-line warning and counted in the
  summary instead of dumping a stack trace.

## v6.6.2

### 💥 Breaking Changes

- Existing timestamp files will mismatch once after this upgrade because the
  stored config changed shape. Either let the first timestamped run re-examine
  each tree once, or run once with `-N` (`--timestamps-no-check-config`) to keep
  the old stamps.

### 🐛 Fixed

- Timestamps are no longer silently invalidated when options come from a tree
  root's `.picopt.yaml` instead of identical CLI flags: the config check now
  compares each tree's effective configuration, directory configs included.
- `timestamps: true` in a tree root's `.picopt.yaml` (e.g. written by `-W -t`)
  now enables timestamping for that tree without `-t`. CLI flags still win, and
  `--dry-run` / `--list` still disable stamping.
- Timestamp invalidation is now per tree and value-based: comment or formatting
  edits to `.picopt.yaml` files, rewriting them with `-W`, or running with a
  different set of top paths no longer invalidate stamps — only actual option
  changes do.
- Discarding stamps because the configuration changed now prints a warning
  naming the differing options instead of silently re-optimizing.
- Verbose timestamps, ignores, after, and memory budget summaries are no longer
  repeated once per directory when using per-directory `.picopt.yaml` files.

## v6.6.1

### 🐛 Fixed

- Animated WebP images with zero-duration frames no longer fail to optimize.
- The `Optimizing formats` summary is no longer repeated once per directory when
  using `-W` or per-directory `.picopt.yaml` files.

## v6.6.0

### 💥 Breaking Changes

- Existing timestamps are invalidated once after upgrading because the timestamp
  config check gained new keys; the first `-t` run re-examines already-optimized
  trees.

### ✨ Added

- Per-directory `.picopt.yaml` config files: pin any setting to a directory
  tree. Deeper directories win; environment variables and the command line still
  override. Editing one re-processes its tree on timestamped runs.
- Write your invoked options to config files: `-w` to the user config, `-W` to a
  `.picopt.yaml` in each target directory, `--write-config-file PATH` to an
  explicit path.
- Memory-aware scheduling: picopt now estimates the peak memory of large
  archives and limits how many run at once so big libraries (e.g. multi-GB comic
  archives) no longer exhaust RAM and get the process OOM-killed. Tune the
  budget with the new `--memory-limit` option (e.g. `--memory-limit 8G`), which
  reads as an approximate peak-memory target; the default is two-thirds of
  detected RAM.
- Incremental archive re-optimization: when a timestamped archive changes,
  members older than its timestamp are skipped instead of re-optimized; `-E`
  disables the member check. Timestamp files found inside archives are consumed
  and removed on repack.

### ♻️ Changed

- Archive member format detection runs in parallel workers instead of
  serializing the scheduler.
- Solid 7z archives extract in one pass instead of decompressing from the start
  for every member.
- The progress pre-scan is skipped in quiet mode, less image data is shipped
  between processes, and scheduling under a memory limit no longer rescans the
  whole queue on every completion.

### 🐛 Fixed

- Files are now replaced atomically: a crash, kill, or full disk mid-write can
  no longer destroy the original image.
- Archive members whose optimization fails are kept in the repacked archive;
  previously they were silently dropped.
- Nested archives (e.g. a CBZ inside a ZIP) now optimize; previously they always
  errored.
- Archives keep their comments and member order through repack; tar symlinks and
  hardlinks survive; 7z member times are preserved; pre-1980 member times no
  longer crash conversion; legacy non-UTF8 zip member names are repaired.
- Archive conversions compress each member by content; converting a rar, tar, or
  7z no longer leaves every member stored uncompressed.
- Files that fail to optimize are retried on the next timestamped run;
  previously directory timestamps covered them and they were skipped forever.
- One corrupt file inside an archive (e.g. a decompression bomb) no longer
  aborts the entire run.
- Boolean options set in config files or environment variables are no longer
  ignored.
- Requested archive conversions (e.g. CBR to CBZ) now happen even when the
  contents are already optimized.
- Lossless WebPs with large metadata inside archives are no longer misdetected
  as lossy.
- Owner-password-restricted PDFs keep their encryption; optimized PDF images
  keep their color transform; more signed PDFs are detected and refused.
- svgo no longer strips viewBox, and keeps title/desc metadata unless
  `--strip-metadata` is given.
- Conversions discarded for being bigger (and dry runs) are reported as skips,
  not errors.
- `--preserve` no longer fails as a non-root user when it cannot change
  ownership; it still restores permissions and modification time.
- Temporary files and animated-WebP frame directories are cleaned up when a tool
  fails or a run is cancelled, instead of leaking to disk.
- `picopt doctor` no longer reports missing tools and exits nonzero on healthy
  installs.
- Symlink loops, unreadable directories, and FIFOs no longer hang or crash the
  walk.
- Bad `--memory-limit` and `--after` values abort with clean error messages;
  timezone-aware `--after` values are honored; lowercase format lists are
  accepted for `-x` and `-c`.
- `-I`/`--no-default-ignores` without `-i` no longer aborts at startup.

## v6.5.2

### 🧑‍💻 Developer

- Update to latest oxipng v10

## v6.5.1

### ✨ Added

- Show platform-specific install hints in `picopt doctor` for missing tools.

### 🐛 Fixed

- Fix data loss when converting without external tools.

## v6.5.0

### ♻️ Changed

- Faster PDF detection
- Faster metadata extraction
- Defer animated image duration doublecheck to only WebP animated and only at
  handler time. Speeds up other animated images.
- Use rich\_argparse to format cli help.

## v6.4.0

### 🧑‍💻 Developer

- Update to Confuse 2.2.0
- Introduce new PicoptSettings class to type the config.

## v6.3.1

### 🐛 Fixed

- Fix frame duration erroneously extracted for MPO format, causing an error.

## v6.3.0

### ♻️ Changed

- New progress and logging

## v6.2.0

### ✨ Added

- Add bunx support for svgo

### ♻️ Changed

- Print stack traces when errors occur.

### 🐛 Fixed

- Fix multiprocessing crash when using timestamps with some archives.

## v6.1.1

### 🧑‍💻 Developer

- Treestamps 3.0.0

## v6.1.0

### ✨ Added

- Added fail fast options for the entire workflow or only containers.

### ♻️ Changed

- Rewote multiprocessing to enable more throughput.

## v6.0.0

### ✨ Added

- Picopt now recompresses PDFs and their image contents losslessly.
- Picopt doctor command shows what optimization tools are available.

### ♻️ Changed

- Picopt now skips writing timestamps if no other disk writing operation
  occurred.

### 🧑‍💻 Developer

- New architecture uses discoverable plugins to keep behavior contained in
  plugin files rather than spread out across the codebase.

## v5.3.2

### ✨ Added

- Add option --timestamps-ignore-archive-entry-mtimes.
- Add type hints and py.typed sentinel file.

## v5.3.1

### 🐛 Fixed

- Fix incompatibility with Confuse v2.2.0

### 🧑‍💻 Developer

- Pin to Confuse v2.1.0 due to typing issues with Confuse v2.2.0

## v5.3.0

### ✨ Added

- Use webpmux if available to unpack and repack animated webp images.
- Use img2webp if available for animated conversion to webp from png.

### ♻️ Changed

- Use memory buffers instead of disk for webp output.

### 🐛 Fixed

- Fix Animated WebP images
    - Sometimes being repacked in reverse frame order.
    - Sometimes degrading quality.
    - Sometimes dropping frames.

### 🔒 Security

- Use secure python temporary directory for unpacking animated webp images and
  chaining webp conversion input.

## v5.2.2

### ✨ Added

- Support Python 3.14

## v5.2.1

### ♻️ Changed

- The confuse library dependency doesn't support Python 3.14. So neither does
  picopt :(

## v5.2.0

### ♻️ Changed

- MozJpeg is now an internal python module. External mozjpeg & jpegtran support
  removed.

## v5.1.1

### 🐛 Fixed

- Fix verbosity default too high.

## v5.1.0

### ♻️ Changed

- Use gif2webp to convert GIFs to WebP. It saves space compared to picopt's
  custom method.

## v5.0.1

### 🐛 Fixed

- Fix crash converting animated images with bad duration metadata.

## v5.0.0

### 💥 Breaking Changes

- Timestamps options changed, invalidating old timestamps. On your first run in
  a path with picopt 5.0 you may use the `-N` option to ignore the old
  timestamp's config differences.
- -T --test option becomes -d --dry-run

### ✨ Added

- Picopt learned to optimize 7-Zip and Tar Archives.

### ♻️ Changed

- Ignore dotfiles by default. Disable with -I.
- colors changed.
- Archives skipped without unpacking contents if all contents are skippable.
- Animated pngs better optimized with oxipng
- Faster scanning for legacy timestamps on startup.

### 🐛 Fixed

- Fix tif & animated gifs were not converted to pngs when specified.
- Fix --ignore option wildcards and performance.
- \--ignore is now case insensitive on case insenstitive filesystems

### 🧑‍💻 Developer

- Updated treestamps
- uv build system

## v4.0.4

### ✨ Added

- Pillow 11 support.
- README Redhat installation and spelling fixes by @bpepple

### ♻️ Changed

- Better jpeg xmp preservation.

### 🐛 Fixed

- Fix crash on reporting some errors.

## v4.0.3 - Bad release

## v4.0.2

### 🐛 Fixed

- Fix windows mmap crash. Thanks @Fletcher.

## v4.0.1

### ♻️ Changed

- Reduce overzealous png optimization. Provide an option to do that.

## v4.0.0

### 💥 Breaking Changes

- Timestamps options changed, invalidating old timestamps. On your first run in
  a path with picopt 4.0 use the `-N` option to ignoring the old timestamp.
- `--destroy-metadata` option becomes `--strip-metadata`

### ✨ Added

- Support optimizing SVG with svgo.
- Support converting more lossless formats to PNG & WEBP: CUR, DIB, FITS, IMT,
  PCX, PIXAR, PSD, QOI, SGI, SPIDER, SUN, TGA, XBM, XPM.
- Support converting animated formats to animated PNG.
- Support converting losslessly converting MPO to JPEG (choose primary image)
- `--near-lossless` option for lossless WebP.
- `--preserve` file attributes after optimization.
- `--disable-programs` option.

### ♻️ Changed

- Internal oxipng replaces external optipng for png compression.
- Better support for preserving EXIF, ICC\_PROFILE, & XMP data across
  optimization and conversion.
- \~25% faster due to avoiding disk io.

### 🐛 Fixed

- wal file would write illegal key names and fail to load for some files.

### 🧑‍💻 Developer

- walk.run now returns totals instead of running report on them.

## v3.3.7

### ♻️ Changed

- Improve WebP optimization.

### 🔥 Removed

- Remove Lossy WebP optimization. Wasn't optimal.

### 🐛 Fixed

- Fix non zero exit code on success.

## v3.3.6

### ✨ Added

- Support zip deflate64

### 🐛 Fixed

- If unrar is not available do not convert rar. Was making empty zips.

## v3.3.5

### 🐛 Fixed

- Wasn't skipping directories appropriately.

## v3.3.4

### 🐛 Fixed

- Keep original path suffix if not converting.

## v3.3.3

### 🐛 Fixed

- Update treestamps fixes bugs.

## v3.3.2

### ♻️ Changed

- Upstream treestamps returns to relative stamp paths for portability.

## v3.3.1

### 🐛 Fixed

- Upstream treestamps fixes crashes and check\_config option.

## v3.3.0

### ✨ Added

- New option to disable treestamps check of config section for a run.

### 🧑‍💻 Developer

- Update deps including treestamps.

## v3.2.6

### ♻️ Changed

- Simple error message instead of stack trace on config failure.

### 🐛 Fixed

- Fix cleanup of temp dir when repacking a container or animated images fails.

## v3.2.5

### 🐛 Fixed

- Fix occasionally removing both final and originals on case insensitive
  filesystem.

## v3.2.4

### 🐛 Fixed

- Fix error reporting
- Fix WebP Lossless detection

## v3.2.3

### ♻️ Changed

- Color help. Change bigger color to blue.

## v3.2.2

### 🐛 Fixed

- Remove more debug print statements.

## v3.2.1

### 🐛 Fixed

- Remove debug print statements.

## v3.2.0

### ✨ Added

- Animated PNG conversion to WEBP support
- Highlight conversions with color output
- Lowlight nothing saved results with dark colors
- Report on unhandled formats at verbosity > 1.

### ♻️ Changed

- Suppress stdout from programs
- Report errors in more detail

### 🐛 Fixed

- Fixed showing total saved at the end
- Fixed verbosity count for cli

## v3.1.4

### 🐛 Fixed

- Remove extraneous debug print statement.

## v3.1.3

### ✨ Added

- Add progress dots to verbose level 1

### 🐛 Fixed

- Fix not deleting working files

## v3.1.2

### 🐛 Fixed

- Fix treestamps factory breaking.

## v3.1.1

### ✨ Added

- Add verbose logging skip files reason.

### 🐛 Fixed

- Fix not skipping older than timestamp files.

## v3.1.0

### ♻️ Changed

- Change walk algorithm to complete directories and containers before opening
  new ones.
- Case insensitive format config.

### 🐛 Fixed

- Ignore symlinks when asked to in timestamps.

## v3.0.5

### ♻️ Changed

- Don't record timestamps for items inside containers.
- Traverse directories alphabetically.

### 🐛 Fixed

- Timestamps respect ignore option.

## v3.0.4

### 🐛 Fixed

- Fix timestamps not recording sometimes.

## v3.0.3

### ♻️ Changed

- Don't dump full timestamps after every dir completes.

## v3.0.2

### 🐛 Fixed

- Trap container repack errors.

## v3.0.1

### 🧑‍💻 Developer

- Update treestamps to accept string paths.

## v3.0.0

### 💥 Breaking Changes

- Changed cli option names.

### ✨ Added

- WebP lossless, lossy and animated support.
- Gain support for .zip archives
- EPub support. ePub contents are never converted.
- TIFF support
- Picopt will convert and clean up old style timestamps.
- Timestamps record configuration. Running with a new config invalidates
  non-matching timestamps.
- .picoptrc.yaml files can configure options
- Fall back to Pillow optimization if better external programs not found.
- Colored terminal output.

### ♻️ Changed

- Timestamps are now kept in .picopt\_treestamps.yaml files.
- Timestamps are now recorded after optimizing every image for each image
  individually instead of directories, preserving progress.
- Faster checking for external programs
- optiping optimization level changed to o5

### 🔥 Removed

- Removed cli args for manually disabling programs

### 🐛 Fixed

- Cleans up old temporary files from aborted picopt runs.
- Fix condition where new files in an old archive were not processed.
- Exif & icc metadata preserved in all formats much better by default.

## v2.2.1

### ✨ Added

- Support python v3.9

### 🐛 Fixed

- Preserve comments when optimizing comic archives

## v2.2.0

### ♻️ Changed

- Walk in alphabetical order

### 🧑‍💻 Developer

- Check code with vulture and radon

## v2.1.0

### ♻️ Changed

- Don't preserve ctime/mtime when making new pngs

### 🔥 Removed

- Remove adv support.
- Remove jpegrescan support. Inferior to mozjpeg

### 🧑‍💻 Developer

- Use pytest instead of nosetest
- Require formatting with black & isort

## v2.0.1

### 🐛 Fixed

- Pillow 7 compatibility

## v2.0.0

### 💥 Breaking Changes

- Stop supporting python 2

### 🧑‍💻 Developer

- Switch to poetry build system
- Type checking with mypy

## v1.6.3

### 🐛 Fixed

- Don't use pngout on 16 bit pngs because it crashes
- Fix broken option -D --optimize\_after

## v1.6.2

### 🐛 Fixed

- Fix illegal stack trace call.

## v1.6.1

### 🐛 Fixed

- Fix exception handling when extern process returns non-zero

## v1.6.0

### ✨ Added

- Python3 proof

### ♻️ Changed

- Report on all errors at the end

### 🔥 Removed

- Remove PIL support in favor of Pillow.

## v1.5.3

### 🐛 Fixed

- Fix hang on external program error. Likely with 16 bit PNGs and pngout.

## v1.5.2

### ✨ Added

- More compatibility with Python 3

### 🐛 Fixed

- Fix formats as a list when it should be a set issue

## v1.5.1

### 🔥 Removed

- Drop TIFF support.

### 🐛 Fixed

- Fix space savings reporting bug where savings always equaled zero

## v1.4.5

### 🐛 Fixed

- When setting new timestamps, don't remove timestamps above the root paths
  specified as input

## v1.4.4

### ♻️ Changed

- Use timestamp caching more often

## v1.4.3

### 🐛 Fixed

- Fix bug where files were not detected
- Fix broken timestamp processing.

## v1.4.1

### 🐛 Fixed

- fix main entry bug for cli

## v1.4.0

### ✨ Added

- let the cli run programmatically with passed in args

### ♻️ Changed

- let the archive date override the newness of its contained files.
- don't redetect new image format type

### 🔥 Removed

- -d --directory argument goes away

### 🐛 Fixed

- code no longer relies on cwd for finding its way

### 🧑‍💻 Developer

- nosetests now run the old inadequate cli tests
- big code cleanup

## v1.3.3

### ✨ Added

- Print found picopt timestamps

### 🐛 Fixed

- Fix jpeg\_multithread flag

### 🧑‍💻 Developer

- Lots of linting
- moved tests out of picopt module

## v1.3.2

### 🧑‍💻 Developer

- Keep **version** in one place in picopt/**init**.py

## v1.3.1

### 🧑‍💻 Developer

- Remove dev dependencies from installed requirements.

## v1.3

### 🧑‍💻 Developer

- break up monolithic picopt into modules. No functional change.

## v1.2

### ✨ Added

- picopt learned the -j option for specifying number of subprocesses (thanks
  @DarwinAwardWinner)

## v1.1.3

### 🐛 Fixed

- fixed rare crash on sequential gif detection

## v1.1.2

### 🐛 Fixed

- detect PNM images properly for conversion with optipng

## v1.1.1

### 🐛 Fixed

- fix verifying gif crash (thanks @DarwinAwardWinner)

## v1.1.0

### ✨ Added

- mozjpeg support (thanks to @crass00)

## v1.0.6

### 🐛 Fixed

- Fix disabled comic archive switch.

## v1.0.5

### 🐛 Fixed

- Fix timestamp writing to happen once workers have finished
- Fix size saved if size in is zero

## v1.0.3

### 🐛 Fixed

- Fix -v to actually be more verbose than default
- Fix from Dennis Schwertel to jpegtran runner

## v1.0.2

### 🐛 Fixed

- Fix -Y to actually disable not enable type conversion

## v1.0.1

### 🐛 Fixed

- Fix typos in --help

## v1.0.0

### 💥 Breaking Changes

- CHANGED COMMAND LINE ARGUMENT LETTERS.

### ✨ Added

- Packaging for PyPI
- Added verbosity setting

### ♻️ Changed

- Truncated relative and in-archive path names for readibiliy
- Nag about animated gifs less

### 🧑‍💻 Developer

- Internal changes to make picopt more modular and library friendly

## v0.12.0.1

### 🐛 Fixed

- Fix error on no directories

## v0.12.0

### ✨ Added

- Added multithreaded jpegrescan operation when picopt isn't using up all the
  cores at the suggestion of Alex Roe.
- Added destroy metadata option at the suggestion of Alex Roe.

## v0.11.4

### ✨ Added

- Added to ArchLinux by Alex Roe.
