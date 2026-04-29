"""
Typed runtime config for picopt.

Confuse 2.2.0 made ``AttrDict`` a proper generic; an unparameterized
``AttrDict`` resolves to ``AttrDict[str, object]``, and downstream sites
like ``bool(cfg.flag)`` or ``int(cfg.workers)`` no longer type-check.

The fix is to stop passing ``AttrDict`` around. ``confuse`` still parses
YAML / env vars / CLI overrides and validates types via ``MappingTemplate``;
the validated result is converted into this dataclass once in
:meth:`PicoptConfig.get_config`. Every downstream module then takes
``PicoptSettings`` instead of ``AttrDict``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import re
    from pathlib import Path


__all__ = ("ComputedSettings", "IgnorePatterns", "PicoptSettings")


@dataclass(frozen=True, slots=True)
class IgnorePatterns:
    """
    Compiled ignore regexps populated by ``_set_ignore``.

    Each pattern may be ``None`` when the user provided no ``ignore``
    list and ``ignore_defaults=False``.
    """

    case: re.Pattern[str] | None
    ignore_case: re.Pattern[str] | None


@dataclass(frozen=True, slots=True)
class ComputedSettings:
    """
    Computed-at-startup state that downstream code reads off the config.

    - ``handler_stages`` is filled by :class:`ConfigHandlers` after probing
      each handler's PIPELINE; absence of a handler-class key signals
      "no available pipeline" to the routing layer. Typed as ``dict[Any, Any]``
      to avoid an import cycle with ``picopt.plugins.base``; consumers know
      the concrete shape via local ``cast``-style usage.
    - ``ignore`` is filled by ``_set_ignore`` from the user's ``ignore``
      list plus ``ignore_defaults``.
    """

    handler_stages: dict[Any, Any]
    ignore: IgnorePatterns


@dataclass(frozen=True, slots=True)
class PicoptSettings:
    """
    Validated picopt runtime config.

    Built once by :meth:`PicoptConfig.get_config` from the confuse
    ``MappingTemplate`` output; consumed by every downstream module.
    Field types match the runtime types confuse produces; ``Sequence(...)``
    template entries become ``tuple[X, ...]`` since the dataclass is frozen.
    """

    # User-facing scalar options
    bigger: bool
    dry_run: bool
    fail_fast: bool
    fail_fast_container: bool
    ignore_defaults: bool
    jobs: int
    keep_metadata: bool
    list_only: bool
    near_lossless: bool
    png_max: bool
    preserve: bool
    recurse: bool
    symlinks: bool
    timestamps: bool
    timestamps_check_config: bool
    timestamps_ignore_archive_entry_mtimes: bool
    verbose: int

    # Sequences
    disable_programs: tuple[str, ...]
    formats: tuple[str, ...]
    ignore: tuple[str, ...]
    paths: tuple[Path, ...]

    # Optional
    after: float | None
    convert_to: tuple[str, ...] | None
    extra_formats: tuple[str, ...] | None

    # Computed (populated by config-time helpers)
    computed: ComputedSettings
