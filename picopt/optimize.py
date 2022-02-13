"""Optimize a file."""
import shutil
import traceback

from pathlib import Path
from typing import Callable, Optional, Tuple, Type

from picopt import PROGRAM_NAME, detect_format, files, stats
from picopt.extern import ExtArgs
from picopt.formats.format import Format
from picopt.formats.gif import GIF_FORMATS, Gif
from picopt.formats.jpeg import JPEG_FORMATS, Jpeg
from picopt.formats.png import Png
from picopt.formats.webp import ANIMATED_WEBP_FORMAT, WEBP_FORMAT, AnimatedWebP, WebP
from picopt.settings import Settings
from picopt.stats import ReportStats


TMP_SUFFIX = f".{PROGRAM_NAME}-optimized"


def _optimize_image_external(
    settings: Settings,
    path: Path,
    func: Callable[[ExtArgs], str],
    image_format: str,
    new_ext: str,
) -> ReportStats:
    """Optimize the file with the external function."""
    new_filename = str(path) + TMP_SUFFIX + new_ext
    new_path = Path(new_filename).resolve()
    shutil.copy2(path, new_path)

    ext_args = ExtArgs(
        str(path), str(new_path), image_format, settings.destroy_metadata
    )
    new_image_format = func.__func__(ext_args)  # type: ignore

    if new_image_format == ANIMATED_WEBP_FORMAT:
        new_image_format = WEBP_FORMAT

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


def _get_format_module(settings: Settings, image_format: str) -> Optional[Type[Format]]:
    """Get the format module to use for optimizing the image."""
    format_cls: Optional[Type[Format]] = None
    # TODO should detect_format return the Format module?
    # TODO make sure this doesn't change formats by default

    if detect_format.is_format_selected(
        settings, image_format, settings.to_webp_formats, WebP.PROGRAMS
    ):
        format_cls = WebP
    elif detect_format.is_format_selected(
        settings, image_format, settings.to_png_formats, Png.PROGRAMS
    ):
        format_cls = Png
    elif detect_format.is_format_selected(
        settings, image_format, JPEG_FORMATS, Jpeg.PROGRAMS
    ):
        format_cls = Jpeg
    elif detect_format.is_format_selected(
        settings, image_format, settings.to_animated_webp_formats, AnimatedWebP.PROGRAMS
    ):
        format_cls = AnimatedWebP
    elif detect_format.is_format_selected(
        settings, image_format, GIF_FORMATS, Gif.PROGRAMS
    ):
        # this captures still GIFs too if not caught above
        format_cls = Gif

    return format_cls


def optimize_image(arg: Tuple[Path, str, Settings]) -> ReportStats:
    """Optimize a given image from a filename."""
    path = Path()
    try:
        path, image_format, settings = arg

        format_cls = _get_format_module(settings, image_format)

        if format_cls is None:
            if settings.verbose > 1:
                print(path, image_format)
                print("\tFile format not selected.")
            return stats.ReportStats(path, error="File format not selected.")

        report_stats = _optimize_with_progs(settings, format_cls, path, image_format)
        stats.report_saved(settings, report_stats)
        return report_stats
    except Exception as exc:
        print(exc)
        traceback.print_exc()
        return stats.ReportStats(path, error="Optimizing Image")
