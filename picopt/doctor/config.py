"""
Check that the layered config loads and says what the user meant.

Reads the raw source stack from :meth:`PicoptConfig.layer_sources` for
provenance and unknown keys, because the ``_set_*`` normalizers hide where a
value came from. Settings come from the same build a run uses, without its
config writes.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from difflib import get_close_matches
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from confuse import ConfigSource, EnvSource
from confuse.exceptions import ConfigError

from picopt import PROGRAM_NAME
from picopt import plugins as registry
from picopt.config import (
    DEFAULT_MEMORY_FRACTION,
    PicoptConfig,
    config_keys,
    detect_total_ram,
    parse_memory_str,
)
from picopt.doctor.result import (
    FAIL,
    INFO,
    OK,
    WARN,
    CheckResult,
    describe,
    display_path,
)

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import Iterable

    from confuse import Configuration

    from picopt.config.settings import PicoptSettings

SECTION: Final = "Config"
_MIB: Final = 1024**2
_GIB: Final = 1024**3
# Reported per target in the Paths section instead.
_PROVENANCE_SKIP_KEYS: Final = frozenset({"paths"})
_WRITE_FLAGS: Final = (
    ("write_config", "-w"),
    ("write_dir_config", "-W"),
    ("write_config_file", "--write-config-file"),
)


@dataclass(frozen=True, slots=True)
class ConfigReport:
    """The Config section's rows, and the run-level settings if they built."""

    results: tuple[CheckResult, ...]
    picopt_config: PicoptConfig
    settings: PicoptSettings | None


class SourceLabels:
    """Name each config source the way a user would recognize it."""

    def __init__(self, layered: Configuration, arguments: Namespace) -> None:
        """Note the user config and -C paths to tell file sources apart."""
        self.user_path: str = os.path.abspath(layered.user_config_path())  # noqa: PTH100
        cli_path = arguments.picopt.config
        self.cli_path: str | None = (
            os.path.abspath(cli_path)  # noqa: PTH100
            if cli_path
            else None
        )

    def label(self, source: ConfigSource) -> str | None:
        """Return a source's label; None for the packaged defaults."""
        if source.default:
            return None
        if isinstance(source, EnvSource):
            return "env"
        filename = source.filename
        if filename is None:
            return "command line"
        if filename == self.user_path:
            return f"user config {display_path(filename)}"
        if filename == self.cli_path:
            return f"-C {display_path(filename)}"
        return display_path(filename)


# ── Unknown keys ──────────────────────────────────────────────────────


def _suggestion(key: str, valid: Iterable[str]) -> str:
    matches = get_close_matches(key, sorted(valid), n=1)
    return f"did you mean {matches[0]}?" if matches else "ignored"


def _where(source: ConfigSource, label: str, *keys: str) -> str:
    """Name a key so the user can find it: an env var, or key and file."""
    if isinstance(source, EnvSource):
        return source.prefix + source.sep.join(keys).upper()
    return f"{'.'.join(keys)} ({label})"


def unknown_key_rows(
    source: ConfigSource, label: str, valid: frozenset[str], section: str = SECTION
) -> list[CheckResult]:
    """WARN for each key in a source that picopt will silently ignore."""
    rows: list[CheckResult] = []
    for raw_key, value in source.items():
        key = str(raw_key)
        if key != PROGRAM_NAME:
            nest = f"; nest it under {PROGRAM_NAME}:" if key in valid else ""
            detail = f"{_where(source, label, key)}: ignored{nest}"
            rows.append(CheckResult(section, f"outside {PROGRAM_NAME}:", WARN, detail))
            continue
        if not isinstance(value, Mapping):
            continue
        for raw_sub_key in value:
            sub_key = str(raw_sub_key)
            if sub_key in valid:
                continue
            where = _where(source, label, key, sub_key)
            detail = f"{where}: {_suggestion(sub_key, valid)}"
            rows.append(CheckResult(section, "unknown key", WARN, detail))
    return rows


def _unknown_keys(layered: Configuration, labels: SourceLabels) -> list[CheckResult]:
    valid = config_keys()
    rows: list[CheckResult] = []
    for source in layered.sources:
        label = labels.label(source)
        # argparse already rejects unknown flags.
        if label is None or label == "command line":
            continue
        rows.extend(unknown_key_rows(source, label, valid))
    return rows


# ── Provenance ────────────────────────────────────────────────────────


def format_value(value: Any) -> str:
    """Show a config value the way it would be written in YAML."""
    match value:
        case bool():
            return str(value).lower()
        case list() | tuple() | set() | frozenset():
            return "[" + ", ".join(format_value(item) for item in value) + "]"
        case None:
            return "null"
        case _:
            return str(value)


def _provenance(layered: Configuration, labels: SourceLabels) -> list[CheckResult]:
    """INFO for each option set somewhere other than the packaged defaults."""
    view = layered[PROGRAM_NAME]
    rows: list[CheckResult] = []
    for key in sorted(config_keys() - _PROVENANCE_SKIP_KEYS):
        try:
            value, source = view[key].first()
        except ConfigError:
            continue
        if (label := labels.label(source)) is not None:
            detail = f"{format_value(value)}  from {label}"
            rows.append(CheckResult(SECTION, key, INFO, detail))
    return rows


# ── Settings checks ───────────────────────────────────────────────────


def _known_tool_names() -> frozenset[str]:
    return frozenset(
        tool.name
        for handler_cls in registry.all_handlers()
        for tier in handler_cls.PIPELINE
        for tool in tier
        if tool.name
    )


def _disable_programs_rows(settings: PicoptSettings) -> list[CheckResult]:
    """WARN for each disable_programs entry that matches no tool."""
    # Matching is exact, as in config.handlers._pick_tier_tool.
    known = _known_tool_names()
    rows: list[CheckResult] = []
    for name in settings.disable_programs:
        if name in known:
            continue
        detail = f"'{name}' matches no tool: {_suggestion(name, known)}"
        rows.append(CheckResult(SECTION, "disable_programs", WARN, detail))
    return rows


def _memory_row(layered: Configuration, settings: PicoptSettings) -> CheckResult:
    """Report the memory budget and how it was derived."""
    budget = f"{settings.memory_limit // _MIB} MiB"
    raw = layered[PROGRAM_NAME]["memory_limit"].get()
    limit = parse_memory_str(raw)
    if limit is not None and limit > 0:
        return CheckResult(SECTION, "memory budget", INFO, f"{budget} (set to {raw})")
    total = detect_total_ram()
    fraction = Fraction(DEFAULT_MEMORY_FRACTION).limit_denominator(10)
    ram = f"{total.total / _GIB:.0f} GiB"
    if not total.detected:
        detail = f"{budget} (auto: {fraction} of an assumed {ram}; RAM not detected)"
        fix = "set --memory-limit, e.g. 8G"
        return CheckResult(SECTION, "memory budget", WARN, detail, fix)
    return CheckResult(
        SECTION, "memory budget", INFO, f"{budget} (auto: {fraction} of {ram})"
    )


# ── Section ───────────────────────────────────────────────────────────


def _file_rows(labels: SourceLabels) -> list[CheckResult]:
    user_path = display_path(labels.user_path)
    if Path(labels.user_path).is_file():
        rows = [CheckResult(SECTION, "user config", OK, user_path)]
    else:
        rows = [CheckResult(SECTION, "user config", INFO, f"none at {user_path}")]
    if labels.cli_path:
        rows.append(CheckResult(SECTION, "-C file", OK, display_path(labels.cli_path)))
    return rows


def _write_flag_rows(arguments: Namespace) -> list[CheckResult]:
    return [
        CheckResult(SECTION, flag, WARN, "ignored: the doctor never writes")
        for key, flag in _WRITE_FLAGS
        if getattr(arguments.picopt, key, None)
    ]


def _read_failure(exc: Exception) -> CheckResult:
    """Return the error a run reports before exiting 78, as a FAIL row."""
    # confuse's read errors name the file.
    detail = str(exc) if isinstance(exc, ConfigError) else describe(exc)
    return CheckResult(SECTION, "read", FAIL, detail)


def check_config(arguments: Namespace) -> ConfigReport:
    """Load the run's config the way a run would and report what's wrong."""
    picopt_config = PicoptConfig()
    rows = _write_flag_rows(arguments)
    try:
        layered = PicoptConfig.layer_sources(arguments)
    except Exception as exc:
        rows.append(_read_failure(exc))
        return ConfigReport(tuple(rows), picopt_config, None)
    labels = SourceLabels(layered, arguments)
    rows = [*_file_rows(labels), *rows, *_unknown_keys(layered, labels)]
    settings: PicoptSettings | None = None
    try:
        # The run's build and validation, without get_config's writes.
        settings = picopt_config.get_dir_settings(arguments, ())
    except ConfigError as exc:
        rows.append(CheckResult(SECTION, "invalid", FAIL, str(exc)))
    except Exception as exc:
        rows.append(CheckResult(SECTION, "invalid", FAIL, describe(exc)))
    if settings is not None:
        rows.extend(_disable_programs_rows(settings))
        rows.append(_memory_row(layered, settings))
    rows.extend(_provenance(layered, labels))
    return ConfigReport(tuple(rows), picopt_config, settings)
