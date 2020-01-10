"""Settings class for picopt."""
import multiprocessing
import time

from argparse import Namespace
from multiprocessing.pool import Pool
from pathlib import Path
from typing import Callable
from typing import List
from typing import Optional
from typing import Set

import dateutil.parser

from . import extern


class Settings(Namespace):
    """Global settings class."""

    DEFAULT_FORMATS = "ALL"
    # advpng: bool = False
    archive_name: Optional[str] = None
    bigger: bool = False
    comics: bool = False
    destroy_metadata: bool = False
    follow_symlinks: bool = True
    formats: Set[str] = set()
    gifsicle: bool = True
    ignore: List[str] = []
    jobs: int = multiprocessing.cpu_count()
    jpegrescan: bool = True
    jpegrescan_multithread: bool = False
    jpegtran: bool = True
    jpegtran_prog: bool = True
    list_only: bool = False
    mozjpeg: bool = True
    optimize_after: Optional[float] = None
    optipng: bool = True
    paths: Set[str] = set()
    pngout: bool = True
    record_timestamp: bool = False
    recurse: bool = False
    test: bool = False
    to_png_formats: Set[str] = set()
    verbose: int = 1
    pool: Pool = multiprocessing.Pool()

    def __init__(
        self,
        programs: Optional[Set[Callable]] = None,
        namespace: Optional[Namespace] = None,
    ) -> None:
        """Initialize settings object with arguments namespace."""
        self._update(namespace)
        self._config_program_reqs(programs)
        self.verbose += 1
        self.paths = set(self.paths)
        self._update_formats()
        self._update_optimize_after()
        self.jobs = max(self.jobs, 1)
        self._set_jpegrescan_threading()

    def _update_optimize_after(self) -> None:
        if self.optimize_after is None:
            return
        try:
            after_dt = dateutil.parser.parse(str(self.optimize_after))
            self.optimize_after = time.mktime(after_dt.timetuple())
            if self.verbose:
                print("Optimizing after", after_dt)
        except Exception as ex:
            print(ex)
            print("Could not parse date to optimize after.")
            exit(1)

    def _update_formats(self) -> None:
        """Update the format list from to_png_formats & comics flag."""
        from .formats.comic import Comic
        from .formats.gif import Gif
        from .formats.jpeg import Jpeg
        from .formats.png import Png

        if not self.to_png_formats:
            self.to_png_formats = Png.CONVERTABLE_FORMATS
        if not self.formats:
            self.formats = self.to_png_formats | Jpeg.FORMATS | Gif.FORMATS
        if self.comics:
            self.formats |= Comic.FORMATS

        print("Optimizing formats:", *self.formats)

    def _set_jpegrescan_threading(self) -> None:
        """
        Make a rough guess about weather or not to invoke multithreading.

        jpegrescan '-t' uses three threads
        """
        files_in_paths = 0
        non_file_in_paths = False
        for filename in self.paths:
            path = Path(filename)
            if path.is_file():
                files_in_paths += 1
            elif path.exists():
                non_file_in_paths = True
            else:
                print(f"'{filename}' does not exist.")
                exit(1)

        self.jpegrescan_multithread = (
            not non_file_in_paths and self.jobs - (files_in_paths * 3) > -1
        )

    def _update(self, namespace: Optional[Namespace]) -> None:
        """Update settings with a dict."""
        if not namespace:
            return
        for key, val in namespace.__dict__.items():
            if key.startswith("_"):
                continue
            setattr(self, key, val)

    def _set_program_defaults(self, programs: Optional[Set[Callable]]) -> None:
        """Run the external program tester on the required binaries."""
        if not programs:
            from .formats.gif import Gif
            from .formats.jpeg import Jpeg
            from .formats.png import Png

            programs = set(Png.PROGRAMS + Gif.PROGRAMS + Jpeg.PROGRAMS)
        for program in programs:
            prog_name = program.__func__.__name__  # type: ignore
            val = getattr(self, prog_name) and extern.does_external_program_run(
                prog_name, Settings.verbose
            )
            setattr(self, prog_name, val)

    def _config_program_reqs(
        self, programs: Optional[Set[Callable[[extern.ExtArgs], str]]]
    ) -> None:
        """Run the program tester and determine if we can do anything."""
        self._set_program_defaults(programs)

        do_png = self.optipng or self.pngout  # or self.advpng
        do_jpeg = self.mozjpeg or self.jpegrescan or self.jpegtran

        do_comics = self.comics

        if not (do_png or do_jpeg or do_comics):
            print("All optimizers are not available or disabled.")
            exit(1)
