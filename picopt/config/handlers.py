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

Important ordering invariant: ``CWebPTool.probe()`` records on the
shared ``CWEBP_TOOL`` singleton whether cwebp is modern, and WebP handler
instances read that flag in ``__init__`` to widen their accepted input
formats. The probe loop runs at config-construction time, before
:class:`Walk` ever instantiates a handler, so the flag is always in place
by the time it matters. Don't reorder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from picopt import plugins as registry

if TYPE_CHECKING:
    from collections.abc import Iterable

    from confuse import Subview

    from picopt.plugins.base import Handler, Tool


def _pick_tier_tool(
    tier: tuple[Tool, ...],
    disabled_program_names: frozenset[str],
) -> Tool | None:
    """Return the first available, non-disabled tool in a tier."""
    for tool in tier:
        if tool.name and tool.name in disabled_program_names:
            continue
        if tool.probe().available:
            return tool
    return None


def _select_pipeline_for_handler(
    handler_cls: type[Handler],
    disabled_program_names: frozenset[str],
) -> tuple[Tool, ...] | None:
    """
    Probe each tier of a handler's pipeline; return chosen tools or None.

    Returns ``None`` if any tier has no available tool — that signals the
    handler can't run on this machine. Returns the empty tuple for handlers
    with an empty pipeline (e.g. archive packers that use only stdlib /
    library code); those are unconditionally available. Tiers whose tools
    are all optional are skipped when nothing in them is available.
    """
    chosen: list[Tool] = []
    for tier in handler_cls.PIPELINE:
        picked = _pick_tier_tool(tier, disabled_program_names)
        if picked is not None:
            chosen.append(picked)
        elif any(tool.required for tool in tier):
            return None
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

    @staticmethod
    def _get_config_set(config: Subview, *keys: str) -> frozenset[str]:
        val_list: list[str] = []
        for key in keys:
            if key in config:
                val_list += config[key].get(list) or []
        return frozenset(val.upper() for val in val_list)

    @staticmethod
    def _print_formats_config(
        verbose: int,
        handled_format_strs: set[str],
        convert_format_strs: dict[str, set[str]],
    ) -> None:
        if not verbose:
            return
        handled_list = ", ".join(sorted(handled_format_strs))
        logger.info(f"Optimizing formats: {handled_list}")
        for target, sources in convert_format_strs.items():
            if not sources:
                continue
            from_list = ", ".join(sorted(sources))
            logger.info(f"Converting {from_list} to {target}")

    def _set_format_handler_stages(
        self,
        handler_cls: type[Handler],
        handler_stages: dict[type[Handler], tuple[Tool, ...]],
        disabled_program_names: frozenset[str],
    ) -> None:
        stages = _select_pipeline_for_handler(handler_cls, disabled_program_names)
        if stages is not None:
            handler_stages[handler_cls] = stages

    def set_format_handler_map(self, config: Subview) -> None:
        """Probe handlers for the requested formats and store availability."""
        all_format_strs = self._get_config_set(config, "formats", "extra_formats")
        config["formats"].set(tuple(sorted(all_format_strs)))
        convert_to = self._get_config_set(config, "convert_to")
        # Write the upcased lists back so template validation accepts
        # lowercase user input for -x and -c exactly as it does for -f.
        if extra_formats := self._get_config_set(config, "extra_formats"):
            config["extra_formats"].set(tuple(sorted(extra_formats)))
        if convert_to:
            config["convert_to"].set(tuple(sorted(convert_to)))

        disabled_list: list[str] | None = config["disable_programs"].get(list)
        disabled_program_names = (
            frozenset(disabled_list) if disabled_list else frozenset()
        )

        handler_stages: dict[type[Handler], tuple[Tool, ...]] = {}
        for handler_cls in _enabled_handler_classes(all_format_strs):
            self._set_format_handler_stages(
                handler_cls, handler_stages, disabled_program_names
            )
        # Build the verbose-output summary with the routing layer's own
        # decision function so the log can never drift from what the walk
        # actually does. repack=True for archives applies the same
        # convert/CAN_PACK gates the repack pass will.
        handled_format_strs: set[str] = set()
        convert_format_strs: dict[str, set[str]] = {}
        routes = registry.routes_by_format()
        for file_format, (native, convert_chain) in routes.items():
            if file_format.format_str not in all_format_strs:
                continue
            picked = registry.pick_route_handler(
                file_format,
                native,
                convert_chain,
                convert=True,
                repack=file_format.archive,
                convert_to=convert_to,
                handler_stages=handler_stages,
            )
            if picked is None:
                continue
            handled_format_strs.add(file_format.format_str)
            if picked is not native:
                convert_format_strs.setdefault(picked.OUTPUT_FORMAT_STR, set()).add(
                    file_format.format_str
                )
        config["computed"]["handler_stages"].set(handler_stages)

        verbose: int = config["verbose"].get(int)
        self._print_formats_config(verbose, handled_format_strs, convert_format_strs)
