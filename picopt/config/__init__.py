"""
Confuse config for picopt.

The format-handler routing map is no longer built here — it lives in the
plugin registry. The only computed values that survive in this file are
``ignore`` regexps, the parsed ``after`` timestamp, and the per-handler
``handler_stages`` populated by :class:`ConfigHandlers`.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from confuse import Configuration, MappingTemplate
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
from picopt import plugins as registry
from picopt.config.handlers import ConfigHandlers

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import Iterable

    from confuse import Subview


def _build_template() -> MappingTemplate:
    """
    Build the confuse template using registry-derived format choices.

    Deferred to a function so the registry can finish discovery before the
    Choice() validators are constructed.
    """
    all_format_strs = registry.all_format_strs()
    convert_to_format_strs = registry.convert_target_format_strs()
    return MappingTemplate(
        {
            PROGRAM_NAME: MappingTemplate(
                {
                    "after": Optional(float),
                    "bigger": bool,
                    "convert_to": Optional(Sequence(Choice(convert_to_format_strs))),
                    "disable_programs": Sequence(str),
                    "dry_run": bool,
                    "extra_formats": Optional(Sequence(Choice(all_format_strs))),
                    "formats": Sequence(Choice(all_format_strs)),
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
                    "timestamps_ignore_archive_entry_mtimes": bool,
                    "verbose": Integer(),
                    "computed": Optional(
                        MappingTemplate(
                            {
                                "handler_stages": dict,
                                "ignore": Optional(
                                    MappingTemplate(
                                        {
                                            "case": re.Pattern,
                                            "ignore_case": re.Pattern,
                                        }
                                    )
                                ),
                            }
                        )
                    ),
                }
            )
        }
    )


_MULTIPLE_STARS_RE: re.Pattern[str] = re.compile(r"\*+")
_DEFAULT_IGNORE_REGEXPS = (r"^\.", r"\/\.", r"\.sparsebundle$")


class PicoptConfig(ConfigHandlers):
    """Construct Picopt Config."""

    def _set_after(self, config: Subview) -> None:
        after = config["after"].get()
        if after is None:
            return
        try:
            timestamp = float(after)
        except ValueError:
            after_dt = parse(after)
            timestamp = time.mktime(after_dt.timetuple())
        config["after"].set(timestamp)
        after = time.ctime(timestamp)
        self._printer.config(f"Optimizing after {after}")

    @staticmethod
    def _get_ignore_regexp(
        ignore_list: list[str],
        verbose: int,
        *,
        ignore_defaults: bool,
    ) -> tuple[str, list[str]]:
        ignore_regexps: list[str] = []
        if ignore_defaults:
            ignore_regexps += _DEFAULT_IGNORE_REGEXPS
        ignore_single_stars: list[str] = []
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

    def _print_ignores(
        self, ignore_single_stars: list[str], *, ignore_defaults: bool
    ) -> None:
        ignore_text = ""
        if ignore_single_stars:
            ignore_text = "Ignoring: " + ",".join(ignore_single_stars)
        if not ignore_defaults:
            if ignore_single_stars:
                ignore_text += " "
            ignore_text += "Not ignoring dotfiles."
        if ignore_text:
            self._printer.config(ignore_text)

    def _set_ignore(self, config: Subview) -> None:
        """Compute ignore regexp."""
        ignore_list: list[str] = sorted(frozenset(config["ignore"].get(list)))
        ignore_defaults: bool = config["ignore_defaults"].get(bool)
        verbose: int = config["verbose"].get(int)
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
        verbose: int = config["verbose"].get(int)
        if verbose > 1:
            if timestamps:
                roots: set[Path] = set()
                paths: Iterable = config["paths"].get(list)
                for path_str in paths:
                    path = Path(path_str)
                    roots.add(path if path.is_dir() else path.parent)
                roots_str = ", ".join(sorted(str(p) for p in roots))
                ts_str = f"Setting a timestamp file at the top of each directory tree: {roots_str}"
            else:
                ts_str = "Not setting timestamps."
            self._printer.config(ts_str)

    def get_config(
        self, args: Namespace | None = None, modname: str = PROGRAM_NAME
    ) -> AttrDict:
        """Get the config dict, layering env and args over defaults."""
        config = Configuration(PROGRAM_NAME, modname=modname, read=False)
        config.read()
        if args and getattr(args, "picopt", None) and args.picopt.config:
            config.set_file(args.picopt.config)
        config.set_env()
        if args:
            config.set_args(args)
        config_program = config[PROGRAM_NAME]
        self._set_ignore(config_program)
        self._set_after(config_program)
        self._set_timestamps(config_program)
        self.set_format_handler_map(config_program)
        ad = config.get(_build_template())
        return ad.picopt
