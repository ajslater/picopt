"""Confuse config for picopt."""

import re
import time
from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING

from confuse import Configuration, MappingTemplate, Subview
from confuse.templates import (
    AttrDict,
    Choice,
    Integer,
    Optional,
    Sequence,
)
from confuse.templates import (
    Path as ConfusePath,
)
from dateutil.parser import parse
from termcolor import cprint

from picopt import PROGRAM_NAME
from picopt.config.consts import ALL_FORMAT_STRS, CONVERT_TO_FORMAT_STRS
from picopt.config.handlers import set_format_handler_map

if TYPE_CHECKING:
    from collections.abc import Iterable

_TEMPLATE = MappingTemplate(
    {
        PROGRAM_NAME: MappingTemplate(
            {
                "after": Optional(float),
                "bigger": bool,
                "convert_to": Optional(Sequence(Choice(CONVERT_TO_FORMAT_STRS))),
                "disable_programs": Sequence(str),
                "dry_run": bool,
                "extra_formats": Optional(Sequence(Choice(ALL_FORMAT_STRS))),
                "formats": Sequence(Choice(ALL_FORMAT_STRS)),
                "ignore": Sequence(str),
                "ignore_dotfiles": bool,
                "jobs": Integer(),
                "keep_metadata": bool,
                "list_only": bool,
                "near_lossless": bool,
                "paths": Sequence(ConfusePath()),
                "png_max": bool,
                "preserve": bool,
                "recurse": bool,
                "symlinks": bool,
                "timestamps": bool,
                "timestamps_check_config": bool,
                "verbose": Integer(),
                "computed": Optional(
                    MappingTemplate(
                        {
                            "native_handlers": dict,
                            "convert_handlers": dict,
                            "handler_stages": dict,
                            "ignore": Optional(
                                MappingTemplate(
                                    {
                                        "case": re.Pattern,
                                        "ignore_case": re.Pattern,
                                    }
                                )
                            ),
                            "is_modern_cwebp": bool,
                        }
                    )
                ),
            }
        )
    }
)
_MULTIPLE_STARS_RE = re.compile(r"\*+")
_DOTFILE_REGEXPS = (r"^\.", r"\/\.")


def _set_after(config: Subview) -> None:
    after = config["after"].get()
    if after is None:
        return

    try:
        timestamp = float(after)  # type: ignore[reportArgumentType]
    except ValueError:
        after_dt = parse(after)  # type: ignore[reportArgumentType]
        timestamp = time.mktime(after_dt.timetuple())

    config["after"].set(timestamp)
    if timestamp is not None:
        after = time.ctime(timestamp)
        cprint(f"Optimizing after {after}")


def _get_ignore_regexp(
    ignore_list: list[str],
    verbose: int,
    *,
    ignore_dotfiles: bool,
):
    ignore_regexps = []
    if ignore_dotfiles:
        ignore_regexps += _DOTFILE_REGEXPS

    ignore_single_stars = []
    for ignore_glob in ignore_list:
        ignore_regexp = _MULTIPLE_STARS_RE.sub(r":", ignore_glob)
        ignore_regexp = re.escape(ignore_regexp)
        ignore_regexp = ignore_regexp.replace(":", ".*")
        ignore_regexp = f"^{ignore_regexp}$"
        ignore_regexps.append(ignore_regexp)
        if verbose > 1:
            ignore_single_star = _MULTIPLE_STARS_RE.sub(r"*", ignore_glob)
            ignore_single_stars.append(ignore_single_star)

    return r"|".join(ignore_regexps), ignore_single_stars


def _print_ignores(ignore_single_stars: list[str], *, ignore_dotfiles: bool):
    ignore_text = ""
    if ignore_single_stars:
        ignore_text = "Ignoring: "
        ignore_text += ",".join(ignore_single_stars)
    if not ignore_dotfiles:
        if ignore_single_stars:
            ignore_text += " "
        ignore_text += "Not ignoring dotfiles."
    if ignore_text:
        cprint(ignore_text, "cyan")


def _set_ignore(config: Subview) -> None:
    """Compute ignore regexp."""
    ignore_list: list | tuple | set | frozenset = config["ignore"].get(list)  # type: ignore[reportAssignmentType]
    ignore_list = sorted(frozenset(ignore_list))
    ignore_dotfiles: bool = config["ignore_dotfiles"].get(bool)  # type: ignore[reportAssignmentType]
    verbose: int = config["verbose"].get(int)  # type: ignore[reportAssignmentType]
    ignore_regexp, ignore_single_stars = _get_ignore_regexp(
        ignore_list, verbose, ignore_dotfiles=ignore_dotfiles
    )
    ignore = re.compile(ignore_regexp) if ignore_regexp else None
    ignore_ignore_case = (
        re.compile(ignore_regexp, re.IGNORECASE) if ignore_regexp else None
    )
    config["computed"]["ignore"]["case"].set(ignore)
    config["computed"]["ignore"]["ignore_case"].set(ignore_ignore_case)
    if verbose > 1:
        _print_ignores(ignore_single_stars, ignore_dotfiles=ignore_dotfiles)


def _set_timestamps(config: Subview) -> None:
    """Set the timestamps attribute."""
    timestamps = (
        config["timestamps"].get(bool)
        and not config["dry_run"].get(bool)
        and not config["list_only"].get(bool)
    )
    config["timestamps"].set(timestamps)
    verbose: int = config["verbose"].get(int)  # type: ignore[reportAssignmentType]
    if verbose > 1:
        if timestamps:
            roots = set()
            paths: Iterable = config["paths"].get(list)  # type: ignore[reportAssignmentType]
            for path_str in paths:
                path = Path(path_str)
                if path.is_dir():
                    roots.add(str(path))
                else:
                    roots.add(str(path.parent))
            roots_str = ", ".join(sorted(roots))
            ts_str = f"Setting a timestamp file at the top of each directory tree: {roots_str}"
        else:
            ts_str = "Not setting timestamps."
        cprint(ts_str, "cyan")


def get_config(args: Namespace | None = None, modname=PROGRAM_NAME) -> AttrDict:
    """Get the config dict, layering env and args over defaults."""
    config = Configuration(PROGRAM_NAME, modname=modname, read=False)
    config.read()
    if args and args.picopt and args.picopt.config:
        config.set_file(args.picopt.config)
    config.set_env()
    if args:
        config.set_args(args)
    config_program = config[PROGRAM_NAME]
    _set_ignore(config_program)
    _set_after(config_program)
    _set_timestamps(config_program)
    set_format_handler_map(config_program)
    ad = config.get(_TEMPLATE)
    if not isinstance(ad, AttrDict):
        msg = "Not a valid config"
        raise TypeError(msg)
    return ad.picopt
