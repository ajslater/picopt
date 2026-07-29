"""
Confuse config for picopt.

The format-handler routing map is no longer built here — it lives in the
plugin registry. The only computed values that survive in this file are
``ignore`` regexps, the parsed ``after`` timestamp, and the per-handler
``handler_stages`` populated by :class:`ConfigHandlers`.
"""

from __future__ import annotations

import os
import re
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from confuse import Configuration, MappingTemplate
from confuse.exceptions import ConfigError
from confuse.templates import (
    Choice,
    Integer,
    Optional,
    Sequence,
)
from confuse.templates import (
    Path as ConfusePath,
)
from dateutil.parser import parse
from loguru import logger
from ruamel.yaml import YAML, YAMLError

from picopt import PROGRAM_NAME
from picopt import plugins as registry
from picopt.config.consts import DIR_CONFIG_FILENAME
from picopt.config.handlers import ConfigHandlers
from picopt.config.settings import (
    ComputedSettings,
    IgnorePatterns,
    PicoptSettings,
)
from picopt.log import console

__all__ = ("DIR_CONFIG_FILENAME", "PicoptConfig", "merge_config_file")

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import Iterable

    from confuse import Subview

# CLI args the config writers never persist: the write flags and -C INPUT
# path themselves, paths (argparse requires them on every invocation
# anyway), and the ephemeral run-mode flags dry_run / list_only / verbose —
# persisting those turns a one-off preview or -q into a permanent default
# (a sticky dry_run would make every future run a silent no-op). Users who
# truly want them as defaults can hand-edit the file; they are still
# honored on read.
_UNPERSISTED_ARGS: Final = frozenset(
    {
        "config",
        "paths",
        "write_config",
        "write_dir_config",
        "write_config_file",
        "dry_run",
        "list_only",
        "verbose",
    }
)


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
                    "convert_jpeg_to_jxl": bool,
                    "convert_to": Optional(Sequence(Choice(convert_to_format_strs))),
                    "convert_webp_to_jxl": bool,
                    "disable_programs": Sequence(str),
                    "dry_run": bool,
                    "extra_formats": Optional(Sequence(Choice(all_format_strs))),
                    "fail_fast": bool,
                    "fail_fast_container": bool,
                    "formats": Sequence(Choice(all_format_strs)),
                    "ignore": Sequence(str),
                    "ignore_defaults": bool,
                    "jobs": Integer(),
                    "keep_metadata": bool,
                    "list_only": bool,
                    "memory_limit": Integer(),
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
                                # Patterns are None when the user disables the
                                # default ignores and supplies none (-I alone).
                                "ignore": Optional(
                                    MappingTemplate(
                                        {
                                            "case": Optional(re.Pattern),
                                            "ignore_case": Optional(re.Pattern),
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

# Memory-limit parsing / auto-detection.
_MEMORY_SUFFIXES: dict[str, int] = {
    "K": 1024,
    "M": 1024**2,
    "G": 1024**3,
    "T": 1024**4,
}
# Fraction of total RAM to budget by default. Two-thirds leaves ~a third for the
# OS, file cache, and headroom above the (approximate) per-archive estimate.
_DEFAULT_MEMORY_FRACTION = 2 / 3
# Used only when total RAM can't be detected (e.g. no sysconf, no psutil).
_FALLBACK_TOTAL_RAM = 4 * 1024**3


def _parse_memory_str(value: object) -> int | None:
    """
    Parse a memory size (int bytes or a K/M/G/T-suffixed string) to bytes.

    Returns None for unparseable values so the caller can reject them
    instead of silently falling back to auto-detection.
    """
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().upper().rstrip("B").strip()
    if not text:
        return None
    multiplier = 1
    if text[-1] in _MEMORY_SUFFIXES:
        multiplier = _MEMORY_SUFFIXES[text[-1]]
        text = text[:-1].strip()
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return None


def _detect_total_ram() -> int:
    """Best-effort total physical RAM in bytes, cross-platform."""
    try:
        # POSIX (Linux + macOS): total pages * page size.
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        pass
    try:
        import psutil

        return int(psutil.virtual_memory().total)
    except Exception:
        # Any psutil import/read failure falls back to a safe fixed budget.
        return _FALLBACK_TOTAL_RAM


def _invoked_cli_options(nns: Namespace) -> dict:
    """Return the options explicitly given on the command line."""
    # Unset options are None (argparse flag defaults are None so config
    # layering works), so non-None values are exactly what was invoked.
    # Tuples (from SplitArgsAction) become lists for clean YAML.
    options = {}
    for key, value in vars(nns).items():
        if value is None or key in _UNPERSISTED_ARGS:
            continue
        options[key] = list(value) if isinstance(value, tuple) else value
    return options


def merge_config_file(target: Path, base_path: Path, options: dict) -> None:
    """
    Merge ``options`` into ``base_path``'s config section and write to ``target``.

    Round-trip loads ``base_path`` so existing keys and comments survive,
    then writes owner-only. Raises ``YAMLError`` or ``OSError`` on
    read/write failure so callers decide whether it is fatal.
    """
    yaml = YAML()
    data = yaml.load(base_path.read_text()) if base_path.is_file() else None
    if not isinstance(data, dict):
        data = {}
    section = data.get(PROGRAM_NAME)
    if not isinstance(section, dict):
        section = {}
        data[PROGRAM_NAME] = section
    section.update(options)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w") as stream:
        yaml.dump(data, stream)
    # Best effort: filesystems without POSIX modes (e.g. FAT) just skip it.
    with suppress(OSError):
        target.chmod(0o600)


def _write_merged_config(
    target: Path, base_path: Path, options: dict, verbose: int
) -> None:
    """Write a config for the -w/-W/--write-config-file flags; fatal on failure."""
    try:
        merge_config_file(target, base_path, options)
    except (YAMLError, OSError) as exc:
        logger.error(f"Could not write config file {target}: {exc}")
        sys.exit(1)
    # Confirm this explicitly-requested action at default verbosity, but
    # honor -q (verbose 0) like every other user-facing message.
    if verbose > 0:
        console.print(
            f"Wrote config to {target}", markup=False, highlight=False, soft_wrap=True
        )


def _target_dir_config_paths(paths: Iterable[str]) -> list[Path]:
    """Deduped, order-stable ``.picopt.yaml`` path for each target directory."""
    targets: dict[Path, None] = {}
    for path_str in paths:
        path = Path(path_str)
        # A file target's config lives in its parent directory (matches
        # DirConfig's single-file-target boundary).
        directory = path if path.is_dir() else path.parent
        targets[directory / DIR_CONFIG_FILENAME] = None
    return list(targets)


def _write_configs(config: Configuration, nns: Namespace) -> None:
    """Persist the invoked options per the write flags."""
    options = _invoked_cli_options(nns)
    verbose = config[PROGRAM_NAME]["verbose"].get(int)
    # ``-C`` INPUT is the merge base for the user/explicit-path writes.
    base = Path(nns.config) if nns.config else None
    if nns.write_config:
        target = Path(config.user_config_path())
        _write_merged_config(target, base or target, options, verbose)
    if nns.write_config_file:
        target = Path(nns.write_config_file)
        _write_merged_config(target, base or target, options, verbose)
    if nns.write_dir_config:
        # Each directory config is updated in place; -C is not a base here.
        for target in _target_dir_config_paths(nns.paths):
            _write_merged_config(target, target, options, verbose)


class PicoptConfig(ConfigHandlers):
    """Construct Picopt Config."""

    def _set_after(self, config: Subview, *, print_summary: bool) -> None:
        after = config["after"].get()
        if after is None:
            return
        try:
            timestamp = float(after)
        except ValueError:
            try:
                after_dt = parse(after)
            except (ValueError, OverflowError) as exc:
                msg = f"Unparseable --after value {after!r}: {exc}"
                raise ConfigError(msg) from exc
            # datetime.timestamp() honors an explicit timezone; naive
            # values are interpreted as local time, like mktime did.
            timestamp = after_dt.timestamp()
        config["after"].set(timestamp)
        if print_summary:
            after = time.ctime(timestamp)
            logger.info(f"Optimizing after {after}")

    def _set_memory_limit(self, config: Subview, *, print_summary: bool) -> None:
        """
        Resolve the memory budget (in bytes) used to throttle large archives.

        Accepts an int or a K/M/G/T-suffixed string. ``0`` (the default) means
        auto: two-thirds of detected physical RAM. The resolved value is always
        a positive byte count.
        """
        raw = config["memory_limit"].get()
        limit = _parse_memory_str(raw)
        if limit is None:
            msg = f"Unparseable --memory-limit value: {raw!r}"
            raise ConfigError(msg)
        if limit <= 0:
            limit = int(_detect_total_ram() * _DEFAULT_MEMORY_FRACTION)
        config["memory_limit"].set(limit)
        if print_summary and config["verbose"].get(int) > 1:
            logger.info(f"Memory budget for large archives: {limit // 1024**2} MiB")

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

    @staticmethod
    def _print_ignores(
        ignore_single_stars: list[str], *, ignore_defaults: bool
    ) -> None:
        ignore_text = ""
        if ignore_single_stars:
            ignore_text = "Ignoring: " + ",".join(ignore_single_stars)
        if not ignore_defaults:
            if ignore_single_stars:
                ignore_text += " "
            ignore_text += "Not ignoring dotfiles."
        if ignore_text:
            logger.info(ignore_text)

    def _set_ignore(self, config: Subview, *, print_summary: bool) -> None:
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
        if print_summary and verbose > 1:
            self._print_ignores(ignore_single_stars, ignore_defaults=ignore_defaults)

    @staticmethod
    def _print_timestamps(config: Subview, *, timestamps: bool) -> None:
        if timestamps:
            roots: set[Path] = set()
            paths: Iterable = config["paths"].get(list)
            for path_str in paths:
                path = Path(path_str)
                roots.add(path if path.is_dir() else path.parent)
            roots_str = ", ".join(sorted(str(p) for p in roots))
            ts_str = f"Setting a timestamp file at the top of each directory tree: {roots_str}"
        else:
            ts_str = "Not setting timestamps at the run level."
        logger.info(ts_str)

    def _set_timestamps(self, config: Subview, *, print_summary: bool) -> None:
        """Set the timestamps attribute."""
        timestamps = (
            config["timestamps"].get(bool)
            and not config["dry_run"].get(bool)
            and not config["list_only"].get(bool)
        )
        config["timestamps"].set(timestamps)
        if print_summary and config["verbose"].get(int) > 1:
            self._print_timestamps(config, timestamps=timestamps)

    def _build_config(
        self,
        args: Namespace | None = None,
        dir_config_files: tuple[Path, ...] = (),
        modname: str = PROGRAM_NAME,
        *,
        print_summary: bool = False,
    ) -> Configuration:
        """
        Build a fully-layered, normalized confuse Configuration.

        Sources, lowest→highest priority: packaged defaults, user config,
        the ``-C`` file, each directory ``.picopt.yaml``
        (shallowest→deepest), env vars, CLI args. Each ``set_*`` call
        appends to the confuse source stack, so the directory files sit
        above the user config yet below env/args — deeper directories win
        over shallower ones, and env/CLI still win over every directory
        file. Shared by :meth:`get_config` (no directory files) and
        :class:`picopt.config.dirconfig.DirConfig` (per-directory chain).
        """
        config = Configuration(PROGRAM_NAME, modname=modname, read=False)
        config.read()
        if args and getattr(args, "picopt", None) and args.picopt.config:
            config.set_file(args.picopt.config)
        for dir_config_file in dir_config_files:
            config.set_file(str(dir_config_file))
        config.set_env()
        if args:
            config.set_args(args)
        config_program = config[PROGRAM_NAME]
        self._set_ignore(config_program, print_summary=print_summary)
        self._set_after(config_program, print_summary=print_summary)
        self._set_memory_limit(config_program, print_summary=print_summary)
        self._set_timestamps(config_program, print_summary=print_summary)
        self.set_format_handler_map(config_program, print_summary=print_summary)
        return config

    @staticmethod
    def _config_to_settings(config: Configuration) -> PicoptSettings:
        """Validate against the template and convert to typed settings."""
        ad = config.get(_build_template())
        return _settings_from_attrdict(ad.picopt)

    def get_config(
        self, args: Namespace | None = None, modname: str = PROGRAM_NAME
    ) -> PicoptSettings:
        """Get the validated, frozen settings layered from defaults/env/args."""
        config = self._build_config(args, modname=modname, print_summary=True)
        # Validate (via _config_to_settings) before persisting so a bad
        # command line can't poison a config file. get_config passes no
        # directory files, so -w output round-trips via -C unchanged.
        settings = self._config_to_settings(config)
        nns = getattr(args, "picopt", None) if args else None
        if nns is not None and (
            nns.write_config or nns.write_dir_config or nns.write_config_file
        ):
            _write_configs(config, nns)
        return settings

    def get_dir_settings(
        self,
        args: Namespace | None,
        dir_config_files: tuple[Path, ...],
    ) -> PicoptSettings:
        """
        Resolve settings with per-directory config files layered in.

        Like :meth:`get_config` but for the per-directory chain: the
        directory ``.picopt.yaml`` files layer beneath env/CLI and above
        the user config, and the write flags are never triggered. Used by
        :class:`picopt.config.dirconfig.DirConfig`.
        """
        config = self._build_config(args, dir_config_files)
        return self._config_to_settings(config)


def _settings_from_attrdict(ad: Any) -> PicoptSettings:
    """
    Build a frozen :class:`PicoptSettings` from a validated AttrDict.

    Confuse's ``MappingTemplate`` already normalized the leaf types, but
    confuse 2.2.0's typed ``AttrDict[str, object]`` widens every attribute
    read back to ``object``. ``ad`` is typed as ``Any`` here so this
    conversion — the one place that knows the schema — can read fields
    directly. Downstream code consumes the typed ``PicoptSettings`` only.
    """
    computed = ad.computed
    ignore = computed.ignore
    return PicoptSettings(
        after=ad.after,
        bigger=ad.bigger,
        convert_jpeg_to_jxl=ad.convert_jpeg_to_jxl,
        convert_to=tuple(ad.convert_to) if ad.convert_to is not None else None,
        convert_webp_to_jxl=ad.convert_webp_to_jxl,
        disable_programs=tuple(ad.disable_programs),
        dry_run=ad.dry_run,
        extra_formats=tuple(ad.extra_formats) if ad.extra_formats is not None else None,
        fail_fast=ad.fail_fast,
        fail_fast_container=ad.fail_fast_container,
        formats=tuple(ad.formats),
        ignore=tuple(ad.ignore),
        ignore_defaults=ad.ignore_defaults,
        jobs=ad.jobs,
        keep_metadata=ad.keep_metadata,
        list_only=ad.list_only,
        memory_limit=ad.memory_limit,
        near_lossless=ad.near_lossless,
        paths=tuple(ad.paths),
        png_max=ad.png_max,
        preserve=ad.preserve,
        recurse=ad.recurse,
        symlinks=ad.symlinks,
        timestamps=ad.timestamps,
        timestamps_check_config=ad.timestamps_check_config,
        timestamps_ignore_archive_entry_mtimes=ad.timestamps_ignore_archive_entry_mtimes,
        verbose=ad.verbose,
        computed=ComputedSettings(
            handler_stages=dict(computed.handler_stages),
            ignore=IgnorePatterns(case=ignore.case, ignore_case=ignore.ignore_case),
        ),
    )
