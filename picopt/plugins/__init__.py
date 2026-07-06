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

from picopt.plugins.base import ContainerHandler, Detector, Handler, Plugin

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

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
        if module_info.name.startswith("_") or module_info.name == "base":
            continue
        # Plugins may be single modules or subpackages (e.g. webp/);
        # either way the PLUGIN descriptor lives at the top level.
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
    seen: set[str] = {
        s
        for plugin in iter_plugins()
        for s in (
            *(h.OUTPUT_FORMAT_STR for h in plugin.handlers),
            *(r.file_format.format_str for r in plugin.routes),
            *plugin.extra_format_strs,
        )
    }
    return tuple(sorted(seen))


@cache
def lossless_format_strs() -> frozenset[str]:
    """Format strings that are losslessly compressible."""
    return frozenset(
        s
        for plugin in iter_plugins()
        for s in (
            *(
                r.file_format.format_str
                for r in plugin.routes
                if r.file_format.lossless
            ),
            # PIL_CONVERTIBLE extra formats are all lossless
            *(plugin.extra_format_strs if plugin.name == "PIL_CONVERTIBLE" else ()),
        )
    )


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


def is_pipeline_available(handler_cls: type[Handler], handler_stages: Mapping) -> bool:
    """
    Whether the config-time probe found a workable pipeline for a handler.

    A handler is "available" iff every tier in its ``PIPELINE`` produced a
    selected tool. Handlers with an empty PIPELINE (e.g. archive handlers
    that pack via Python libraries, or PILPack sentinels) are always
    available — there is nothing to be missing.
    """
    if not handler_cls.PIPELINE:
        return True
    return handler_cls in handler_stages


def pick_route_handler(
    file_format: FileFormat | None,
    native: type[Handler] | None,
    convert_chain: tuple[type[Handler], ...],
    *,
    convert: bool,
    repack: bool,
    convert_to: frozenset[str],
    handler_stages: Mapping,
) -> type[Handler] | None:
    """
    Pick the handler class for a format — the one routing decision.

    Used by the factory at runtime and by the config layer to build the
    startup formats summary, so the log can never drift from what the
    walk actually does. Selection: the first convert-chain candidate whose
    output the user asked for and whose pipeline probed available (archives
    only convert during the repack pass), else the native handler if
    available; repack callers additionally require a packing container.
    """
    if file_format is None:
        return None
    handler_cls = _pick_convert_handler(
        convert_chain,
        convert_to,
        handler_stages,
        file_format,
        convert=convert,
        repack=repack,
    )
    if (
        handler_cls is None
        and native is not None
        and is_pipeline_available(native, handler_stages)
    ):
        handler_cls = native
    if repack and not _can_pack_repack(handler_cls):
        handler_cls = None
    return handler_cls


def _can_pack_repack(handler_cls: type[Handler] | None) -> bool:
    """Report whether the handler is a container that can pack itself back up."""
    return (
        handler_cls is not None
        and issubclass(handler_cls, ContainerHandler)
        and handler_cls.CAN_PACK
    )


def _pick_convert_handler(
    convert_chain: tuple[type[Handler], ...],
    convert_to: frozenset[str],
    handler_stages: Mapping,
    file_format: FileFormat,
    *,
    convert: bool,
    repack: bool,
) -> type[Handler] | None:
    """
    First convert candidate the user asked for whose pipeline is available.

    Returns ``None`` when conversion doesn't apply at all: the caller didn't
    request it, or it's an archive outside the repack pass (archives only
    convert while repacking).
    """
    if not convert or (file_format.archive and not repack):
        return None
    for candidate in convert_chain:
        if candidate.OUTPUT_FORMAT_STR not in convert_to:
            continue
        if not is_pipeline_available(candidate, handler_stages):
            continue
        return candidate
    return None
