"""Settings class for picopt."""
import multiprocessing

from pathlib import Path
from typing import Optional, Set

from picopt import PROGRAM_NAME, extern
from picopt.formats.comic_formats import COMIC_FORMATS
from picopt.formats.gif import GIF_FORMATS, Gif
from picopt.formats.jpeg import JPEG_FORMATS, Jpeg
from picopt.formats.png import PNG_FORMATS, Png
from picopt.formats.webp import (
    WEBP_ANIMATED_CONVERTABLE_FORMATS,
    WEBP_FORMATS,
    AnimatedWebP,
    WebP,
)
from picopt.rc.settings_base import SettingsBase


FORMAT_CLASSES = (Gif, Jpeg, Png, WebP, AnimatedWebP)


class Settings(SettingsBase):
    """Picopt settings."""

    _RC_NAME: str = f".{PROGRAM_NAME}rc.yaml"
    _SET_ATTRS: Set[str] = set(
        (
            "formats",
            "paths",
            "to_png_formats",
            "to_webp_formats",
            "to_animated_webp_formats",
        )
    )

    # advpng: bool = False
    bigger: bool = False
    comics: bool = False
    destroy_metadata: bool = False
    follow_symlinks: bool = True
    formats: Set[str] = set()
    gifsicle: bool = True
    jobs: int = multiprocessing.cpu_count()
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
    to_webp_formats: Set[str] = set()
    to_animated_webp_formats: Set[str] = set()
    cwebp: bool = True
    gif2webp: bool = True
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
        if not self.to_png_formats:
            self.to_png_formats = PNG_FORMATS

        if not self.to_animated_webp_formats:
            self.to_animated_webp_formats = WEBP_ANIMATED_CONVERTABLE_FORMATS

        if not self.to_webp_formats:
            self.to_webp_formats = WEBP_FORMATS

        if not self.formats:
            self.formats = (
                self.to_png_formats
                | self.to_webp_formats
                | self.to_animated_webp_formats
                | JPEG_FORMATS
                | GIF_FORMATS
                | WEBP_FORMATS
            )

        if self.comics:
            self.formats |= COMIC_FORMATS

    def _set_program_defaults(self) -> None:
        """Run the external program tester on the required binaries."""
        for cls in FORMAT_CLASSES:
            for program in cls.PROGRAMS:
                prog_name = program.__func__.__name__  # type: ignore
                val = getattr(self, prog_name) and extern.does_external_program_run(
                    prog_name, self.verbose
                )
                setattr(self, prog_name, val)

    def _config_program_reqs(self) -> None:
        """Run the program tester and determine if we can do anything."""
        self._set_program_defaults()

        do_png = self.optipng or self.pngout
        do_jpeg = self.mozjpeg or self.jpegtran
        do_animated_gif = self.gifsicle
        do_comics = self.comics

        self.can_do = do_png or do_jpeg or do_animated_gif or do_comics
