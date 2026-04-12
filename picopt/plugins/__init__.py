"""
Plugin registry.

On first access, the registry imports every module under ``picopt.plugins``
that isn't itself the registry or a base. Each plugin module exposes a
module-level ``PLUGIN`` constant of type :class:`~picopt.plugins.base.Plugin`,
and the registry collects them.

From the collected PLUGIN list, the registry builds the runtime tables that
the rest of picopt asks for: the format → handler routing map, the
default-enabled handler set, the list of advertised --convert-to format
strings, the lossless-format-string set, the per-handler tool inventory for
the doctor command, and the priority-ordered list of non-PIL detectors.

This is the *one and only* place these tables come from. Adding a new format
plugin requires no edits to any other file. Removing one is symmetric.
"""

from __future__ import annotations

import importlib
import pkgutil
from functools import cache
from typing import TYPE_CHECKING

from picopt.plugins.base import Detector, Handler, Plugin

if TYPE_CHECKING:
    from collections.abc import Iterator

    from picopt.plugins.base.format import FileFormat


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


@cache
def _discover() -> tuple[Plugin, ...]:
    """Walk picopt.plugins/ and return every PLUGIN constant found."""
    import picopt.plugins as plugins_pkg

    plugins: list[Plugin] = []
    for module_info in pkgutil.iter_modules(plugins_pkg.__path__):
        if module_info.ispkg:
            continue  # skip the base/ subpackage
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"picopt.plugins.{module_info.name}")
        plugin = getattr(module, "PLUGIN", None)
        if isinstance(plugin, Plugin):
            plugins.append(plugin)
    return tuple(plugins)


def iter_plugins() -> Iterator[Plugin]:
    """Iterate every loaded plugin."""
    yield from _discover()


def plugin_for_handler(handler_cls: type[Handler]) -> Plugin | None:
    """Find the plugin that owns a given handler class."""
    for plugin in iter_plugins():
        if handler_cls in plugin.handlers:
            return plugin
    return None


# ---------------------------------------------------------------------------
# Derived tables (computed once, cached)
# ---------------------------------------------------------------------------


@cache
def all_handlers() -> frozenset[type[Handler]]:
    """Every handler class registered by any plugin."""
    return frozenset(h for plugin in iter_plugins() for h in plugin.handlers)


@cache
def output_handlers() -> frozenset[type[Handler]]:
    """Every handler that produces output (excludes input-only plugins)."""
    return frozenset(
        h for plugin in iter_plugins() if not plugin.input_only for h in plugin.handlers
    )


@cache
def default_handlers() -> frozenset[type[Handler]]:
    """Handlers belonging to plugins enabled by default."""
    return frozenset(
        h
        for plugin in iter_plugins()
        if plugin.default_enabled
        for h in plugin.handlers
    )


@cache
def convert_target_format_strs() -> tuple[str, ...]:
    """Sorted format strings that are valid --convert-to targets."""
    return tuple(
        sorted(
            {
                t.OUTPUT_FORMAT_STR
                for plugin in iter_plugins()
                for t in plugin.convert_targets
            }
        )
    )


@cache
def all_format_strs() -> tuple[str, ...]:
    """Sorted format strings the user can pass to --formats / --extra-formats."""
    seen: set[str] = set()
    for plugin in iter_plugins():
        for handler in plugin.handlers:
            seen.add(handler.OUTPUT_FORMAT_STR)
        for route in plugin.routes:
            seen.add(route.file_format.format_str)
        seen.update(plugin.extra_format_strs)
    return tuple(sorted(seen))


@cache
def lossless_format_strs() -> frozenset[str]:
    """Format strings that are losslessly compressible."""
    out: set[str] = set()
    for plugin in iter_plugins():
        for route in plugin.routes:
            if route.file_format.lossless:
                out.add(route.file_format.format_str)
        if plugin.name == "PIL_CONVERTIBLE":
            # This special case is all lossless
            out.update(plugin.extra_format_strs)
    return frozenset(out)


@cache
def routes_by_format() -> dict[
    FileFormat, tuple[type[Handler] | None, tuple[type[Handler], ...]]
]:
    """
    Build the file_format → (native, convert_chain) routing map.

    Multiple plugins can contribute routes for the same FileFormat (e.g. the
    PIL-convertible plugin contributes routes from BMP/PCX to handlers in
    other plugins). Merging policy:

    - ``native``: at most one per FileFormat, last writer wins. In practice
      every FileFormat in the tree is declared native by exactly one plugin,
      so this never collides.
    - ``convert``: concatenated across plugins, deduplicated preserving the
      first occurrence's position. Order is significant — handler_factory
      will pick the first whose pipeline is available.
    """
    natives: dict[FileFormat, type[Handler] | None] = {}
    converts: dict[FileFormat, list[type[Handler]]] = {}
    for plugin in iter_plugins():
        for route in plugin.routes:
            if route.native is not None:
                natives[route.file_format] = route.native
            convert_list = converts.setdefault(route.file_format, [])
            for convert_handler in route.convert:
                if convert_handler not in convert_list:
                    convert_list.append(convert_handler)
    all_keys = set(natives) | set(converts)
    return {ff: (natives.get(ff), tuple(converts.get(ff, ()))) for ff in all_keys}


@cache
def detectors() -> tuple[type[Detector], ...]:
    """Non-PIL detectors, sorted high-priority first."""
    found: list[type[Detector]] = [
        plugin.detector for plugin in iter_plugins() if plugin.detector is not None
    ]
    return tuple(sorted(found, key=lambda d: -d.PRIORITY))
