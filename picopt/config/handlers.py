"""File Format Handlers Config."""

import shutil
import subprocess
from collections.abc import ItemsView
from dataclasses import dataclass, fields
from types import MappingProxyType

from confuse import Subview
from termcolor import cprint

from picopt.config.cwebp import is_cwebp_modern
from picopt.formats import (
    CONVERTIBLE_PIL_ANIMATED_FILE_FORMATS,
    CONVERTIBLE_PIL_FILE_FORMATS,
    MODERN_CWEBP_FORMAT_STRS,
    MPO_FILE_FORMAT,
    FileFormat,
)
from picopt.handlers.container.animated.webp import WebPAnimatedLossless
from picopt.handlers.container.archive.rar import (
    Cbr,
    Rar,
)
from picopt.handlers.container.archive.seven_zip import (
    Cb7,
    SevenZip,
)
from picopt.handlers.container.archive.tar import (
    Cbt,
    Tar,
    TarBz,
    TarGz,
    TarXz,
)
from picopt.handlers.container.archive.zip import (
    Cbz,
    EPub,
    Zip,
)
from picopt.handlers.handler import INTERNAL, Handler
from picopt.handlers.image.gif import Gif, GifAnimated
from picopt.handlers.image.jpeg import Jpeg
from picopt.handlers.image.png import Png, PngAnimated
from picopt.handlers.image.svg import Svg
from picopt.handlers.image.webp import WebPLossless


@dataclass
class FileFormatHandlers:
    """FileFormat handlers for a File FileFormat."""

    convert: tuple[type[Handler], ...] = ()
    native: tuple[type[Handler], ...] = ()

    def items(self) -> ItemsView[str, tuple[type[Handler], ...]]:
        """Return both fields."""
        return {
            field.name: tuple(getattr(self, field.name)) for field in fields(self)
        }.items()


# Handlers for formats are listed in priority order
_LOSSLESS_CONVERTIBLE_FORMAT_HANDLERS = MappingProxyType(
    {
        ffmt: FileFormatHandlers(convert=(WebPLossless, Png))
        for ffmt in CONVERTIBLE_PIL_FILE_FORMATS
    }
)
_LOSSLESS_CONVERTIBLE_ANIMATED_FORMAT_HANDLERS = MappingProxyType(
    {
        ffmt: FileFormatHandlers(convert=(WebPAnimatedLossless, PngAnimated))
        for ffmt in CONVERTIBLE_PIL_ANIMATED_FILE_FORMATS
    }
)
_FORMAT_HANDLERS = MappingProxyType(
    {
        **_LOSSLESS_CONVERTIBLE_FORMAT_HANDLERS,
        **_LOSSLESS_CONVERTIBLE_ANIMATED_FORMAT_HANDLERS,
        Gif.OUTPUT_FILE_FORMAT: FileFormatHandlers(
            convert=(WebPLossless, Png),
            native=(Gif,),
        ),
        GifAnimated.OUTPUT_FILE_FORMAT: FileFormatHandlers(
            convert=(WebPAnimatedLossless, PngAnimated),
            native=(GifAnimated,),
        ),
        MPO_FILE_FORMAT: FileFormatHandlers(convert=(Jpeg,)),
        Jpeg.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(Jpeg,)),
        Png.OUTPUT_FILE_FORMAT: FileFormatHandlers(
            convert=(WebPLossless,), native=(Png,)
        ),
        PngAnimated.OUTPUT_FILE_FORMAT: FileFormatHandlers(
            convert=(WebPAnimatedLossless,), native=(PngAnimated,)
        ),
        WebPLossless.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(WebPLossless,)),
        WebPAnimatedLossless.OUTPUT_FILE_FORMAT: FileFormatHandlers(
            native=(WebPAnimatedLossless,)
        ),
        Svg.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(Svg,)),
        # Archives
        Zip.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(Zip,)),
        Cbz.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(Cbz,)),
        Rar.INPUT_FILE_FORMAT: FileFormatHandlers(native=(Rar,), convert=(Zip,)),
        Cbr.INPUT_FILE_FORMAT: FileFormatHandlers(native=(Cbr,), convert=(Cbz,)),
        EPub.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(EPub,)),
        SevenZip.INPUT_FILE_FORMAT: FileFormatHandlers(
            native=(SevenZip,), convert=(Zip,)
        ),
        Cb7.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(Cb7,), convert=(Cbz,)),
        Tar.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(Tar,), convert=(Zip,)),
        TarGz.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(TarGz,), convert=(Zip,)),
        TarBz.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(TarBz,), convert=(Zip,)),
        TarXz.OUTPUT_FILE_FORMAT: FileFormatHandlers(native=(TarXz,), convert=(Zip,)),
        Cbt.INPUT_FILE_FORMAT: FileFormatHandlers(native=(Cbt,), convert=(Cbz,)),
    }
)


def _print_formats_config(
    verbose: int,
    handled_format_strs: set[str],
    convert_format_strs: dict[str, set[str]],
    cwebp_version: str,
    *,
    is_modern_cwebp: bool,
) -> None:
    """Print verbose init messages."""
    handled_format_list = ", ".join(sorted(handled_format_strs))
    cprint(f"Optimizing formats: {handled_format_list}")
    for convert_to_format_str, format_strs in convert_format_strs.items():
        convert_from_list = sorted(format_strs)
        if not convert_from_list:
            return
        convert_from = ", ".join(convert_from_list)
        cprint(f"Converting {convert_from} to {convert_to_format_str}", "cyan")
    if (
        verbose > 1
        and not is_modern_cwebp
        and WebPAnimatedLossless.OUTPUT_FORMAT_STR in convert_format_strs
    ):
        to_webp_strs = MODERN_CWEBP_FORMAT_STRS & handled_format_strs
        if to_webp_strs:
            to_web_str = " & ".join(sorted(to_webp_strs))
            cprint(
                f"Converting {to_web_str} with an extra step for older cwebp {cwebp_version}",
                "cyan",
            )


def _get_config_set(config: Subview, *keys: str) -> frozenset[str]:
    val_list = []
    for key in keys:
        val_list += config[key].get(list) if key in config else []  # type: ignore[reportAssignmentType]
    return frozenset(val.upper() for val in val_list)


def _get_handler_stage_npx(program) -> tuple:
    bin_path = shutil.which("npx")
    exec_args = ()
    if not bin_path:
        return exec_args
    exec_args_attempt = (bin_path, "--no", *program.split("_")[1:])
    # Sucks but easiest way to determine if an npx prog exists is
    # running it.
    try:
        subprocess.run(  # noqa: S603
            exec_args_attempt,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        exec_args = exec_args_attempt
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass
    return exec_args


def _get_handler_stage(disabled_programs, program) -> tuple | None:
    exec_args = None
    if program in disabled_programs:
        pass
    elif program.startswith(("pil2", INTERNAL)):
        exec_args = ()
    elif program.startswith("npx_"):
        exec_args = _get_handler_stage_npx(program)
    elif bin_path := shutil.which(program):
        exec_args = (bin_path,)
    return exec_args


def _get_handler_stages(
    handler_class: type[Handler], disabled_programs: frozenset
) -> dict[str, tuple[str, ...]]:
    """Get the program stages for each handler."""
    stages = {}
    for program_priority_list in handler_class.PROGRAMS:
        for program in program_priority_list:
            stage = _get_handler_stage(disabled_programs, program)
            if stage is not None:
                stages[program] = stage
                break
    return stages


def _set_format_handler_map_entry(  # noqa: PLR0913
    handler_type: str,
    handler_class: type[Handler],
    convert_to: frozenset[str],
    handler_stages: dict[type[Handler], dict[str, tuple[str, ...]]],
    convert_format_strs: dict,
    file_format: FileFormat,
    convert_handlers: dict[FileFormat, type[Handler]],
    native_handlers: dict[FileFormat, type[Handler]],
    handled_format_strs: set[str],
    disabled_programs: frozenset,
) -> bool:
    """Create an entry for the format handler maps."""
    if (
        handler_type == "convert"
        and handler_class.OUTPUT_FILE_FORMAT.format_str not in convert_to
    ):
        return False

    # Get handler stages by class with caching
    if handler_class not in handler_stages:
        handler_stages[handler_class] = _get_handler_stages(
            handler_class, disabled_programs
        )
    stages = handler_stages.get(handler_class)
    if not stages:
        return False

    if handler_type == "convert":
        if handler_class.OUTPUT_FORMAT_STR not in convert_format_strs:
            convert_format_strs[handler_class.OUTPUT_FORMAT_STR] = set()
        convert_format_strs[handler_class.OUTPUT_FORMAT_STR].add(file_format.format_str)
        convert_handlers[file_format] = handler_class
    else:
        native_handlers[file_format] = handler_class

    handled_format_strs.add(file_format.format_str)
    return True


def set_format_handler_map(config: Subview) -> None:
    """Create a format to handler map from config."""
    all_format_strs = _get_config_set(config, "formats", "extra_formats")
    config["formats"].set(tuple(sorted(all_format_strs)))
    convert_to = _get_config_set(config, "convert_to")

    native_handlers: dict[FileFormat, type[Handler]] = {}
    convert_handlers: dict[FileFormat, type[Handler]] = {}
    handler_stages: dict[type[Handler], dict[str, tuple[str, ...]]] = {}

    handled_format_strs = set()
    convert_format_strs = {}
    disabled_programs: list | tuple | set | frozenset = config["disable_programs"].get(
        list
    )  # type: ignore[reportAssignmentType]
    disabled_programs = (
        frozenset(disabled_programs) if disabled_programs else frozenset()
    )

    for file_format, possible_file_handlers in _FORMAT_HANDLERS.items():
        if file_format.format_str not in all_format_strs:
            continue
        for (
            handler_type,
            possible_handler_classes,
        ) in sorted(possible_file_handlers.items()):
            for handler_class in possible_handler_classes:
                if _set_format_handler_map_entry(
                    handler_type,
                    handler_class,
                    convert_to,
                    handler_stages,
                    convert_format_strs,
                    file_format,
                    convert_handlers,
                    native_handlers,
                    handled_format_strs,
                    disabled_programs,
                ):
                    break

    is_modern_cwebp, cwebp_version = is_cwebp_modern(handler_stages)

    config["computed"]["native_handlers"].set(native_handlers)
    config["computed"]["convert_handlers"].set(convert_handlers)
    config["computed"]["handler_stages"].set(handler_stages)
    config["computed"]["is_modern_cwebp"].set(is_modern_cwebp)
    verbose: int = config["verbose"].get(int)  # type: ignore[reportAssignmentType]
    _print_formats_config(
        verbose,
        handled_format_strs,
        convert_format_strs,
        cwebp_version,
        is_modern_cwebp=is_modern_cwebp,
    )
