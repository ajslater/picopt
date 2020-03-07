"""Settings class for picopt."""
import multiprocessing
import time

from argparse import Namespace
from typing import Callable
from typing import Optional
from typing import Set

import dateutil.parser

from . import extern


class Settings(Namespace):
    """Global settings class."""

    # advpng: bool = False
    bigger: bool = False
    comics: bool = False
    destroy_metadata: bool = False
    follow_symlinks: bool = True
    formats: Set[str] = set()
    gifsicle: bool = True
    jobs: int = multiprocessing.cpu_count()
    #    jpegrescan: bool = True
    #    jpegrescan_multithread: bool = False
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
        self.jobs = max(self.jobs, 1)

    #        self._set_jpegrescan_threading()

    @staticmethod
    def parse_date_string(date_str: str) -> float:
        """Turn a datetime string into an epoch float."""
        after_dt = dateutil.parser.parse(date_str)
        return time.mktime(after_dt.timetuple())

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

        print("Optimizing formats:", *sorted(self.formats))

    #    def _set_jpegrescan_threading(self) -> None:
    #        """
    #        Make a rough guess about weather or not to invoke multithreading.
    #
    #        jpegrescan '-t' uses three threads
    #        """
    #        files_in_paths = 0
    #        non_file_in_paths = False
    #        for filename in self.paths:
    #            path = Path(filename)
    #            if path.is_file():
    #                files_in_paths += 1
    #            else:
    #                non_file_in_paths = True
    #
    #        self.jpegrescan_multithread = (
    #            not non_file_in_paths and self.jobs - (files_in_paths * 3) > -1
    #        )

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

    def _config_program_reqs(self, programs: Optional[Set[Callable]]) -> None:
        """Run the program tester and determine if we can do anything."""
        self._set_program_defaults(programs)

        do_png = self.optipng or self.pngout  # or self.advpng
        do_jpeg = self.mozjpeg or self.jpegtran  # of self.jpegrescan
        do_comics = self.comics

        self.can_do = do_png or do_jpeg or do_comics
