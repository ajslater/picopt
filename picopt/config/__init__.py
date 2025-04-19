"""Confuse config for picopt."""

import time
from argparse import Namespace
from pathlib import Path
from typing import TYPE_CHECKING

from confuse import Configuration, Subview
from confuse.templates import AttrDict
from dateutil.parser import parse
from termcolor import cprint

from picopt import PROGRAM_NAME
from picopt.config.consts import TEMPLATE
from picopt.config.handlers import set_format_handler_map

if TYPE_CHECKING:
    from collections.abc import Iterable


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


def _set_ignore(config: Subview) -> None:
    """Remove duplicates from the ignore list."""
    ignore: Iterable = config["ignore"].get(list)  # type: ignore[reportAssignmentType]
    ignore = tuple(sorted(ignore))
    config["ignore"].set(ignore)
    if ignore:
        verbose: int = config["verbose"].get(int)  # type: ignore[reportAssignmentType]
        if verbose > 1:
            ignore_list = ",".join(ignore)
            cprint(f"Ignoring: {ignore_list}", "cyan")


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
    set_format_handler_map(config_program)
    _set_after(config_program)
    _set_ignore(config_program)
    _set_timestamps(config_program)
    ad = config.get(TEMPLATE)
    if not isinstance(ad, AttrDict):
        msg = "Not a valid config"
        raise TypeError(msg)
    return ad.picopt
