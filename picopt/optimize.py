"""Optimize a file."""
import shutil
import traceback

from pathlib import Path
from typing import Callable
from typing import Optional
from typing import Tuple
from typing import Type

from . import PROGRAM_NAME
from . import detect_format
from . import files
from . import stats
from .extern import ExtArgs
from .formats.format import Format
from .formats.gif import Gif
from .formats.jpeg import Jpeg
from .formats.png import Png
from .settings import Settings
from .stats import ReportStats


TMP_SUFFIX = f".{PROGRAM_NAME}-optimized"


def _optimize_image_external(
    settings: Settings,
    path: Path,
    func: Callable[[Settings, ExtArgs], str],
    image_format: str,
    new_ext: str,
) -> ReportStats:
    """Optimize the file with the external function."""
    new_filename = str(path) + TMP_SUFFIX + new_ext
    new_path = Path(new_filename).resolve()
    shutil.copy2(path, new_path)

    ext_args = ExtArgs(str(path), str(new_path))
    new_image_format = func.__func__(settings, ext_args)  # type: ignore

    report_stats = files.cleanup_after_optimize(
        settings, path, new_path, image_format, new_image_format
    )
    percent = stats.new_percent_saved(report_stats)
    report = f"{func.__func__.__name__}: {percent}"  # type: ignore
    report_stats.report_list.append(report)

    return report_stats


def _optimize_with_progs(
    settings: Settings, format_cls: Type[Format], path: Path, image_format: str
) -> ReportStats:
    """
    Use the correct optimizing functions in sequence.

    And report back statistics.
    """
    filesize_in = path.stat().st_size
    report_stats = None

    for func in format_cls.PROGRAMS:
        if not getattr(settings, func.__func__.__name__):  # type: ignore
            continue
        report_stats = _optimize_image_external(
            settings, path, func, image_format, format_cls.OUT_EXT
        )
        path = report_stats.final_path
        if format_cls.BEST_ONLY:
            break

    if report_stats is not None:
        report_stats.bytes_in = filesize_in
    else:
        report_stats = stats.skip(image_format, path)

    return report_stats


def _get_format_module(
    settings: Settings, image_format: str
) -> Tuple[Optional[Type[Format]], bool]:
    """Get the format module to use for optimizing the image."""
    format_cls: Optional[Type[Format]] = None
    nag_about_gifs: bool = False

    if detect_format.is_format_selected(
        settings, image_format, settings.to_png_formats, Png.PROGRAMS
    ):
        format_cls = Png
    elif detect_format.is_format_selected(
        settings, image_format, Jpeg.FORMATS, Jpeg.PROGRAMS
    ):
        format_cls = Jpeg
    elif detect_format.is_format_selected(
        settings, image_format, Gif.FORMATS, Gif.PROGRAMS
    ):
        # this captures still GIFs too if not caught above
        format_cls = Gif
        nag_about_gifs = True

    return format_cls, nag_about_gifs


def optimize_image(arg: Tuple[Path, str, Settings]) -> ReportStats:
    """Optimize a given image from a filename."""
    try:
        path, image_format, settings = arg

        format_cls, nag_about_gifs = _get_format_module(settings, image_format)

        if format_cls is None:
            if settings.verbose > 1:
                print(path, image_format)
                print("\tFile format not selected.")
            return stats.ReportStats(path, error="File format not selected.")

        report_stats = _optimize_with_progs(settings, format_cls, path, image_format)
        report_stats.nag_about_gifs = nag_about_gifs
        stats.report_saved(settings, report_stats)
        return report_stats
    except Exception as exc:
        print(exc)
        traceback.print_exc()
        return stats.ReportStats(path, error="Optimizing Image")
