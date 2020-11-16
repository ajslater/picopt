"""Settings class for picopt."""
import multiprocessing

from pathlib import Path
from typing import Optional
from typing import Set

from picopt import PROGRAM_NAME
from picopt import extern
from picopt.settings_base import SettingsBase


class Settings(SettingsBase):
    """Picopt settings."""

    _RC_NAME = f".{PROGRAM_NAME}rc.yaml"
    _SET_ATTRS = set(("formats", "paths", "to_png_formats"))

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
    recurse: bool = True
    test: bool = False
    to_png_formats: Set[str] = set()
    verbose: int = 1

    def load_settings(self, path: Optional[Path]) -> None:
        """Load picopt specific settings as well as the base ones."""
        super().load_settings(path)
        # picopt specific
        self._update_formats()
        if self.verbose > 2:
            print(path, "formats:", *sorted(self.formats))
        self.jobs = max(self.jobs, 1)
        # self._set_jpegrescan_threading()

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
