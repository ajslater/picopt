"""
Configure which handlers and tools are active for this run.

This module replaces the old ~330-line ``config/handlers.py`` with a single
probe-and-select loop:

    for each enabled handler:
        for each tier in handler.PIPELINE:
            pick the first Tool whose probe() returns available
        if every tier produced a Tool:
            store the chosen tuple in config.computed.handler_stages

Handlers whose pipeline can't be filled are simply absent from
``handler_stages``; the routing layer (``walk/handler_factory.py``) reads
that absence as "this handler is unavailable" and falls through the
``Route.convert`` chain.

The format → handler routing map is no longer built here at all — it lives
in the registry as :func:`picopt.plugins.routes_by_format`.

Important ordering invariant: ``CWebPTool.probe()`` mutates
``WebPLossless.IS_MODERN_CWEBP`` as a side effect, and ``WebPLossless``
instances read that flag in ``__init__`` to widen their accepted input
formats. The probe loop runs at config-construction time, before
:class:`Walk` ever instantiates a handler, so the side effect is always in
place by the time it matters. Don't reorder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from picopt import plugins as registry
from picopt.printer import Printer

if TYPE_CHECKING:
    from collections.abc import Iterable

    from confuse import Subview

    from picopt.formats import FileFormat
    from picopt.plugins.base import Handler, Tool


def _select_pipeline_for_handler(
    handler_cls: type[Handler],
    disabled_program_names: frozenset[str],
) -> tuple[Tool, ...] | None:
    """
    Probe each tier of a handler's pipeline; return chosen tools or None.

    Returns ``None`` if any tier has no available tool — that signals the
    handler can't run on this machine. Returns the empty tuple for handlers
    with an empty pipeline (e.g. archive packers that use only stdlib /
    library code); those are unconditionally available.
    """
    if not handler_cls.PIPELINE:
        return ()
    chosen: list[Tool] = []
    for tier in handler_cls.PIPELINE:
        picked: Tool | None = None
        for tool in tier:
            if tool.name and tool.name in disabled_program_names:
                continue
            status = tool.probe()
            if status.available:
                picked = tool
                break
        if picked is None:
            return None
        chosen.append(picked)
    return tuple(chosen)


def _enabled_handler_classes(
    requested_format_strs: frozenset[str],
) -> Iterable[type[Handler]]:
    """
    Every handler whose OUTPUT_FORMAT_STR or input format is requested.

    A handler is "in scope" for probing if any FileFormat it can receive
    appears in the user's --formats / --extra-formats set, OR if its
    OUTPUT_FORMAT_STR does. We probe everything in scope so the routing
    layer has accurate availability info to fall back through.
    """
    for plugin in registry.iter_plugins():
        for handler_cls in plugin.handlers:
            handler_format_strs = {handler_cls.OUTPUT_FORMAT_STR}
            handler_format_strs.update(
                ff.format_str for ff in handler_cls.INPUT_FILE_FORMATS
            )
            if handler_format_strs & requested_format_strs:
                yield handler_cls


class ConfigHandlers:
    """Build the per-handler pipeline selection from the merged config."""

    def __init__(self, printer: Printer | None = None) -> None:
        """Initialize printer."""
        self._printer: Printer = printer or Printer(2)

    @staticmethod
    def _get_config_set(config: Subview, *keys: str) -> frozenset[str]:
        val_list: list[str] = []
        for key in keys:
            if key in config:
                val_list += config[key].get(list) or []
        return frozenset(val.upper() for val in val_list)

    def _print_formats_config(
        self,
        verbose: int,
        handled_format_strs: set[str],
        convert_format_strs: dict[str, set[str]],
    ) -> None:
        if not verbose:
            return
        handled_list = ", ".join(sorted(handled_format_strs))
        self._printer.config(f"Optimizing formats: {handled_list}")
        for target, sources in convert_format_strs.items():
            if not sources:
                continue
            from_list = ", ".join(sorted(sources))
            self._printer.config(f"Converting {from_list} to {target}")

    def _set_format_handler_stages(
        self,
        handler_cls: type[Handler],
        handler_stages,
        disabled_program_names: frozenset[str],
    ):
        stages = _select_pipeline_for_handler(handler_cls, disabled_program_names)
        if stages is not None:
            handler_stages[handler_cls] = stages

    def _set_format_handled_strs_for_format(
        self,
        file_format: FileFormat,
        all_format_strs,
        convert_chain,
        convert_to,
        handler_stages,
        convert_format_strs,
        handled_format_strs,
        native,
    ):
        if file_format.format_str not in all_format_strs:
            return
        picked_via_convert = False
        for candidate in convert_chain:
            if candidate.OUTPUT_FORMAT_STR not in convert_to:
                continue
            if candidate not in handler_stages:
                continue
            convert_format_strs.setdefault(candidate.OUTPUT_FORMAT_STR, set()).add(
                file_format.format_str
            )
            handled_format_strs.add(file_format.format_str)
            picked_via_convert = True
            break
        if not picked_via_convert and native is not None and native in handler_stages:
            handled_format_strs.add(file_format.format_str)

    def set_format_handler_map(self, config: Subview) -> None:
        """Probe handlers for the requested formats and store availability."""
        all_format_strs = self._get_config_set(config, "formats", "extra_formats")
        config["formats"].set(tuple(sorted(all_format_strs)))
        convert_to = self._get_config_set(config, "convert_to")

        disabled_list: list[str] | None = config["disable_programs"].get(list)
        disabled_program_names = (
            frozenset(disabled_list) if disabled_list else frozenset()
        )

        handler_stages: dict[type[Handler], tuple[Tool, ...]] = {}
        for handler_cls in _enabled_handler_classes(all_format_strs):
            self._set_format_handler_stages(
                handler_cls, handler_stages, disabled_program_names
            )
        # Walk the routing table to compute the verbose-output summary. The
        # routing layer will do this same lookup at runtime; we just mirror
        # the result for the user-facing log.
        handled_format_strs: set[str] = set()
        convert_format_strs: dict[str, set[str]] = {}
        routes = registry.routes_by_format()
        for file_format, (native, convert_chain) in routes.items():
            self._set_format_handled_strs_for_format(
                file_format,
                all_format_strs,
                convert_chain,
                convert_to,
                handler_stages,
                convert_format_strs,
                handled_format_strs,
                native,
            )
        config["computed"]["handler_stages"].set(handler_stages)

        verbose: int = config["verbose"].get(int)
        self._print_formats_config(verbose, handled_format_strs, convert_format_strs)
