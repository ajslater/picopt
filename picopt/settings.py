import os
import multiprocessing


class Settings(object):
    advpng = False
    archive_name = None
    bigger = False
    comics = False
    destroy_metadata = False
    dir = os.getcwd()
    follow_symlinks = True
    formats = set()
    gifsicle = True
    jobs = multiprocessing.cpu_count()
    jpegrescan = True
    jpegrescan_mutithread = False
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
    def apply(cls, settings):
        for k, v in settings.__dict__.iteritems():
            if k.startswith('_'):
                continue
            setattr(cls, k, v)
