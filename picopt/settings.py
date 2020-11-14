"""Settings class for picopt."""
import multiprocessing
import time

from argparse import Namespace
from pathlib import Path
from typing import Optional
from typing import Set

import dateutil.parser

from ruamel.yaml import YAML

from picopt import PROGRAM_NAME
from picopt import extern


RC_FN = f".{PROGRAM_NAME}rc.yaml"
_YAML = YAML()


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
    record_timestamp: bool = True
    recurse: bool = False
    test: bool = False
    to_png_formats: Set[str] = set()
    verbose: int = 1
    _SET_ATTRS = set(("formats", "paths", "to_png_formats"))

    def __init__(
        self,
        arg_namespace: Optional[Namespace] = None,
        rc_path: Optional[Path] = None,
        check_programs: bool = False,
    ) -> None:
        """Initialize settings object with arguments namespace."""
        self.arg_namespace = arg_namespace
        if check_programs:
            # only do this once for the whole system
            self._config_program_reqs()
        self.load_settings(rc_path)

    def clone(self, path: Path):
        """Clone this settings for a new path."""
        return Settings(self.arg_namespace, path)

    def load_settings(self, path: Optional[Path]) -> None:
        """Load settings for a path."""
        if path is not None:
            rc_namespace = self.load_rc(path)
            # rc settings write over defaulst
            self._update(rc_namespace)
        # passed in args overwrite rc
        self._update(self.arg_namespace)
        self._update_formats()
        if self.verbose > 1:
            print(path, "formats:", *sorted(self.formats))
        self.jobs = max(self.jobs, 1)
        # self._set_jpegrescan_threading()

    def load_rc(self, path: Path) -> Namespace:
        """Load an rc file, searching recursively upwards."""
        if path.is_file():
            path = path.parent

        rc_path = path / RC_FN

        try:
            rc_settings = _YAML.load(rc_path)
            for attr in self._SET_ATTRS:
                attr_list = rc_settings.get(attr)
                if attr_list is not None:
                    rc_settings[attr] = set(attr_list)
            return Namespace(**rc_settings)
        except Exception as exc:
            print(f"Error parsing {rc_path}")
            print(exc)

        if path == path.parent:
            # at root /, no rc found.
            res = Namespace()
        else:
            res = self.load_rc(path.parent)

        return res

    @staticmethod
    def parse_date_string(date_str: str) -> float:
        """Turn a datetime string into an epoch float."""
        after_dt = dateutil.parser.parse(date_str)
        return time.mktime(after_dt.timetuple())

    def _update_formats(self) -> None:
        """Update the format list from to_png_formats & comics flag."""
        from picopt.formats.comic import Comic
        from picopt.formats.gif import Gif
        from picopt.formats.jpeg import Jpeg
        from picopt.formats.png import Png

        if not self.to_png_formats:
            self.to_png_formats = Png.CONVERTABLE_FORMATS
        if not self.formats:
            self.formats = self.to_png_formats | Jpeg.FORMATS | Gif.FORMATS
        if self.comics:
            self.formats |= Comic.FORMATS

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

    def _set_program_defaults(self) -> None:
        """Run the external program tester on the required binaries."""
        from picopt.formats.programs import PROGRAMS

        for program in PROGRAMS:
            prog_name = program.__func__.__name__  # type: ignore
            val = getattr(self, prog_name) and extern.does_external_program_run(
                prog_name, self.verbose
            )
            setattr(self, prog_name, val)

    def _config_program_reqs(self) -> None:
        """Run the program tester and determine if we can do anything."""
        self._set_program_defaults()

        do_png = self.optipng or self.pngout  # or self.advpng
        do_jpeg = self.mozjpeg or self.jpegtran  # of self.jpegrescan
        do_animated_gif = self.gifsicle
        do_comics = self.comics

        self.can_do = do_png or do_jpeg or do_animated_gif or do_comics
