"""Settings class for picopt."""
import multiprocessing
from argparse import Namespace
from multiprocessing.pool import Pool
from typing import Callable, List, Optional, Set

from . import extern


class Settings(Namespace):
    """Global settings class."""

    advpng: bool = False
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

    @classmethod
    def update(cls, settings: Namespace) -> None:
        """Update settings with a dict."""
        for key, val in settings.__dict__.items():
            if key.startswith('_'):
                continue
            setattr(cls, key, val)

    @classmethod
    def _set_program_defaults(
            cls, programs: Set[Callable[[extern.ExtArgs], str]]) -> None:
        """Run the external program tester on the required binaries."""
        for program in programs:
            prog_name = program.__func__.__name__  # type: ignore
            val = getattr(cls, prog_name) \
                and extern.does_external_program_run(
                        prog_name, Settings.verbose)
            setattr(cls, prog_name, val)

    @classmethod
    def config_program_reqs(
            cls, programs: Set[Callable[[extern.ExtArgs], str]]) -> None:
        """Run the program tester and determine if we can do anything."""
        cls._set_program_defaults(programs)

        do_png = cls.optipng or cls.pngout or cls.advpng
        do_jpeg = cls.mozjpeg or cls.jpegrescan or cls.jpegtran

        do_comics = cls.comics

        if not do_png and not do_jpeg and not do_comics:
            print("All optimizers are not available or disabled.")
            exit(1)
