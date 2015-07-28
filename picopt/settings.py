import os
import multiprocessing


__version__ = 2.0


class Settings(object):
    recurse = False
    verbose = 1
    advpng = False
    comics = False
    formats = set()
    optipng = True
    pngout = True
    mozjpeg = True
    jpegrescan = True
    jpegtran_prog = True
    jpegtran = True
    gifsicle = True
    to_png_formats = set()
    follow_symlinks = True
    dir = os.getcwd()
    bigger = False
    record_timestamp = False
    optimize_after = None
    test = False
    list_only = False
    version = __version__
    destroy_metadata = False
    jobs = multiprocessing.cpu_count()
    paths = set()
    archive_name = None
    jpegrescan_mutithread = False

    @classmethod
    def apply(cls, settings):
        for k, v in settings.__dict__.iteritems():
            if k.startswith('_'):
                continue
            setattr(cls, k, v)
