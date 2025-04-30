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

from picopt import PROGRAM_NAME
from picopt.config.consts import ALL_FORMAT_STRS, CONVERT_TO_FORMAT_STRS
from picopt.config.handlers import ConfigHandlers

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
                "ignore_defaults": bool,
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
_DEFAULT_IGNORE_REGEXPS = (r"^\.", r"\/\.", r"\.sparsebundle$")


class PicoptConfig(ConfigHandlers):
    """Construct Picopt Config."""

    def _set_after(self, config: Subview) -> None:
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
            self._printer.config(f"Optimizing after {after}")

    @staticmethod
    def _get_ignore_regexp(
        ignore_list: list[str],
        verbose: int,
        *,
        ignore_defaults: bool,
    ):
        ignore_regexps = []
        if ignore_defaults:
            ignore_regexps += _DEFAULT_IGNORE_REGEXPS

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

    def _print_ignores(self, ignore_single_stars: list[str], *, ignore_defaults: bool):
        ignore_text = ""
        if ignore_single_stars:
            ignore_text = "Ignoring: "
            ignore_text += ",".join(ignore_single_stars)
        if not ignore_defaults:
            if ignore_single_stars:
                ignore_text += " "
            ignore_text += "Not ignoring dotfiles."
        if ignore_text:
            self._printer.config(ignore_text)

    def _set_ignore(self, config: Subview) -> None:
        """Compute ignore regexp."""
        ignore_list: list | tuple | set | frozenset = config["ignore"].get(list)  # type: ignore[reportAssignmentType]
        ignore_list = sorted(frozenset(ignore_list))
        ignore_defaults: bool = config["ignore_defaults"].get(bool)  # type: ignore[reportAssignmentType]
        verbose: int = config["verbose"].get(int)  # type: ignore[reportAssignmentType]
        ignore_regexp, ignore_single_stars = self._get_ignore_regexp(
            ignore_list, verbose, ignore_defaults=ignore_defaults
        )
        ignore = re.compile(ignore_regexp) if ignore_regexp else None
        ignore_ignore_case = (
            re.compile(ignore_regexp, re.IGNORECASE) if ignore_regexp else None
        )
        config["computed"]["ignore"]["case"].set(ignore)
        config["computed"]["ignore"]["ignore_case"].set(ignore_ignore_case)
        if verbose > 1:
            self._print_ignores(ignore_single_stars, ignore_defaults=ignore_defaults)

    def _set_timestamps(self, config: Subview) -> None:
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
            self._printer.config(ts_str)

    def get_config(
        self, args: Namespace | None = None, modname=PROGRAM_NAME
    ) -> AttrDict:
        """Get the config dict, layering env and args over defaults."""
        config = Configuration(PROGRAM_NAME, modname=modname, read=False)
        config.read()
        if args and args.picopt and args.picopt.config:
            config.set_file(args.picopt.config)
        config.set_env()
        if args:
            config.set_args(args)
        config_program = config[PROGRAM_NAME]
        self._set_ignore(config_program)
        self._set_after(config_program)
        self._set_timestamps(config_program)
        self.set_format_handler_map(config_program)
        ad = config.get(_TEMPLATE)
        if not isinstance(ad, AttrDict):
            msg = "Not a valid config"
            raise TypeError(msg)
        return ad.picopt
