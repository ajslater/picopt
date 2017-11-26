"""Settings class for picopt."""
from __future__ import absolute_import, division, print_function

import multiprocessing

from . import extern


class Settings(object):
    """Global settings class."""

    advpng = False
    archive_name = None
    bigger = False
    comics = False
    destroy_metadata = False
    follow_symlinks = True
    formats = set()
    gifsicle = True
    jobs = multiprocessing.cpu_count()
    jpegrescan = True
    jpegrescan_multithread = False
    jpegtran = True
    jpegtran_prog = True
    list_only = False
    mozjpeg = True
    optimize_after = None
    optipng = True
    paths = set()
    pngout = True
    record_timestamp = False
    recurse = False
    test = False
    to_png_formats = set()
    verbose = 1

    @classmethod
    def update(cls, settings):
        """Update settings with a dict."""
        for key, val in settings.__dict__.items():
            if key.startswith('_'):
                continue
            setattr(cls, key, val)

    @classmethod
    def _set_program_defaults(cls, programs):
        """Run the external program tester on the required binaries."""
        for program in programs:
            val = getattr(cls, program.__name__) \
                and extern.does_external_program_run(program.__name__,
                                                     Settings.verbose)
            setattr(cls, program.__name__, val)

    @classmethod
    def config_program_reqs(cls, programs):
        """Run the program tester and determine if we can do anything."""
        cls._set_program_defaults(programs)

        do_png = cls.optipng or cls.pngout or cls.advpng
        do_jpeg = cls.mozjpeg or cls.jpegrescan or cls.jpegtran

        do_comics = cls.comics

        if not do_png and not do_jpeg and not do_comics:
            print("All optimizers are not available or disabled.")
            exit(1)
