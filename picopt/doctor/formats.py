"""
The effective formats: what a run with these settings does with each one.

Built from :func:`picopt.config.handlers.formats_summary`, the same routing
decision the startup banner and the walk use, so the doctor can't disagree
with a run. An enabled format with no route is a FAIL: the run would skip
every file of it.
"""

from __future__ import annotations

from itertools import groupby
from typing import TYPE_CHECKING, Final

from picopt import plugins as registry
from picopt.config.handlers import (
    FormatRoute,
    enabled_handler_classes,
    formats_summary,
)
from picopt.doctor.result import FAIL, OFF, OK, WARN, CheckResult
from picopt.doctor.tools import install_hint, tool_name

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from picopt.config.settings import PicoptSettings
    from picopt.plugins.base import Handler, Tool

SECTION: Final = "Formats"
_ARROW: Final = " → "


class _Context:
    """The settings every row is judged against."""

    def __init__(self, settings: PicoptSettings) -> None:
        self.settings: PicoptSettings = settings
        self.enabled: frozenset[str] = frozenset(settings.formats)
        self.convert_to: frozenset[str] = frozenset(settings.convert_to or ())
        self.handler_stages: Mapping[type, tuple] = settings.computed.handler_stages
        self.disabled: frozenset[str] = frozenset(settings.disable_programs)
        # The handlers config probed; the rest are absent from handler_stages
        # however healthy their tools are.
        self.probed: frozenset[type[Handler]] = frozenset(
            enabled_handler_classes(self.enabled, self.convert_to)
        )


# ── Describing a route ────────────────────────────────────────────────


def _describe_handler(handler_cls: type[Handler], ctx: _Context) -> str:
    """Name a handler and the tools the run picked for it."""
    stages = ctx.handler_stages.get(handler_cls, ())
    text = handler_cls.__name__
    if stages:
        text += ": " + _ARROW.join(tool_name(tool) for tool in stages)
    stage_set = set(stages)
    missing_optional = [
        tool_name(tool)
        for tier in handler_cls.PIPELINE
        if not any(tool.required for tool in tier) and not stage_set & set(tier)
        for tool in tier
    ]
    if missing_optional:
        text += f" ({', '.join(missing_optional)} missing, optional)"
    return text


def _describe_route(route: FormatRoute, ctx: _Context) -> str:
    picked = route.picked
    if picked is None:
        return ""
    if not route.converts:
        return _describe_handler(picked, ctx)
    text = f"to {picked.OUTPUT_FORMAT_STR} with {_describe_handler(picked, ctx)}"
    if route.file_format.archive and route.native is not None:
        text = f"{_describe_handler(route.native, ctx)}, repacked {text}"
    return text


def _variant(route: FormatRoute) -> str:
    return "animated" if route.file_format.animated else "still"


# ── Explaining a missing route ────────────────────────────────────────


def _missing_tools(handler_cls: type[Handler], ctx: _Context) -> list[Tool]:
    """Tools of the required tiers that left a handler without a pipeline."""
    missing: list[Tool] = []
    for tier in handler_cls.PIPELINE:
        if not any(tool.required for tool in tier):
            continue
        usable = [
            tool
            for tool in tier
            if tool_name(tool) not in ctx.disabled and tool.probe().available
        ]
        if not usable:
            missing.extend(tier)
    return missing


# The usual probe error says only what the tool's name already does.
_NOT_FOUND_SUFFIX: Final = "not found in PATH"


def _tool_reason(tool: Tool, ctx: _Context) -> str:
    """Name a missing tool, with why when it was found but failed its probe."""
    name = tool_name(tool)
    if name in ctx.disabled:
        return f"{name} (disabled)"
    error = tool.probe().error
    if error and not error.endswith(_NOT_FOUND_SUFFIX):
        # -q hides the tool tree, so this row is the only place it shows.
        return f"{name} ({error})"
    return name


def _tool_list(tools: Sequence[Tool], ctx: _Context) -> str:
    return ", ".join(dict.fromkeys(_tool_reason(tool, ctx) for tool in tools))


def _install_fix(tools: Iterable[Tool]) -> str:
    hints = dict.fromkeys(
        hint for tool in tools if (hint := install_hint(tool_name(tool)))
    )
    return "install: " + "; ".join(hints) if hints else ""


def _routed_from(handler_cls: type[Handler]) -> list[str]:
    """List the format strings whose routes lead to a handler."""
    return sorted(
        {
            file_format.format_str
            for file_format, (native, chain) in registry.routes_by_format().items()
            if handler_cls is native or handler_cls in chain
        }
    )


def _why_unavailable(handler_cls: type[Handler], ctx: _Context) -> tuple[str, str]:
    """Explain why a handler isn't usable: (detail, fix)."""
    key = handler_cls.CONFIG_ENABLED_KEY
    if key and not getattr(ctx.settings, key, False):
        return f"needs --{key.replace('_', '-')}", ""
    if handler_cls not in ctx.probed:
        # Config probes every handler an enabled format routes to, so only an
        # opt-in conversion whose source formats are all off lands here.
        return f"needs -x {' or '.join(_routed_from(handler_cls))}", ""
    if tools := _missing_tools(handler_cls, ctx):
        return f"no available tool: {_tool_list(tools, ctx)}", _install_fix(tools)
    return "unavailable", ""


def _explain_requested(
    requested: Sequence[type[Handler]], ctx: _Context
) -> tuple[str, str]:
    """Explain why none of the requested conversions can run."""
    explained = [(h.OUTPUT_FORMAT_STR, *_why_unavailable(h, ctx)) for h in requested]
    reasons = dict.fromkeys(f"-c {target} {detail}" for target, detail, _ in explained)
    fixes = dict.fromkeys(fix for _, _, fix in explained if fix)
    return "; ".join(reasons), "; ".join(fixes)


def _explain_unrouted(route: FormatRoute, ctx: _Context) -> tuple[str, str]:
    """Say why the walk will skip this file format: (detail, fix)."""
    native = route.native
    if native is not None and not registry.is_pipeline_available(
        native, ctx.handler_stages
    ):
        return _why_unavailable(native, ctx)
    if requested := [
        h for h in route.convert_chain if h.OUTPUT_FORMAT_STR in ctx.convert_to
    ]:
        return _explain_requested(requested, ctx)
    kind = "read only" if native is not None else "converts only"
    targets = dict.fromkeys(h.OUTPUT_FORMAT_STR for h in route.convert_chain)
    if not targets:
        return f"{kind}, with nothing to convert to", ""
    return f"{kind}: add -c {' or '.join(targets)}", ""


# ── Rows ──────────────────────────────────────────────────────────────


def _routed_row(
    format_str: str, routed: Sequence[FormatRoute], ctx: _Context, *, many: bool
) -> CheckResult:
    """One OK row naming the handler and tools for each working variant."""
    details = dict.fromkeys(
        (f"{_variant(route)}: " if many else "") + _describe_route(route, ctx)
        for route in routed
    )
    return CheckResult(SECTION, format_str, OK, "; ".join(details))


def _format_rows(
    format_str: str, routes: Sequence[FormatRoute], ctx: _Context
) -> list[CheckResult]:
    """One row for a format, plus a WARN per variant the run will skip."""
    routed = [route for route in routes if route.picked is not None]
    many = len(routes) > 1
    rows = [_routed_row(format_str, routed, ctx, many=many)] if routed else []
    # Every variant skipped is a run that does nothing for this format;
    # one skipped variant among working ones is a gap, not a failure.
    status = WARN if routed else FAIL
    for route in routes:
        if route.picked is not None:
            continue
        detail, fix = _explain_unrouted(route, ctx)
        name = f"{format_str} {_variant(route)}" if many else format_str
        rows.append(CheckResult(SECTION, name, status, detail, fix))
    return rows


def _not_enabled_row(ctx: _Context) -> CheckResult | None:
    others = sorted(set(registry.all_format_strs()) - ctx.enabled)
    if not others:
        return None
    detail = f"{', '.join(others)} (-x FORMAT to add)"
    return CheckResult(SECTION, "not enabled", OFF, detail)


def _convert_to_rows(routes: Sequence[FormatRoute], ctx: _Context) -> list[CheckResult]:
    """WARN for each -c target no enabled format converts to."""
    delivered = {
        route.picked.OUTPUT_FORMAT_STR
        for route in routes
        if route.converts and route.picked is not None
    }
    return [
        CheckResult(
            SECTION, f"-c {target}", WARN, f"no enabled format converts to {target}"
        )
        for target in sorted(ctx.convert_to - delivered)
    ]


def _opt_in_rows(routes: Sequence[FormatRoute], ctx: _Context) -> list[CheckResult]:
    """WARN for each conversion flag that is on but changes nothing."""
    picked = {route.picked for route in routes}
    rows: list[CheckResult] = []
    for handler_cls in sorted(registry.all_handlers(), key=lambda h: h.__name__):
        key = handler_cls.CONFIG_ENABLED_KEY
        if not key or not getattr(ctx.settings, key, False) or handler_cls in picked:
            continue
        target = handler_cls.OUTPUT_FORMAT_STR
        if target not in ctx.convert_to:
            detail = f"has no effect without -c {target}"
        elif handler_cls in ctx.handler_stages:
            detail = "no enabled format converts with it"
        else:
            detail = f"{handler_cls.__name__} {_why_unavailable(handler_cls, ctx)[0]}"
        flag = f"--{key.replace('_', '-')}"
        rows.append(CheckResult(SECTION, flag, WARN, detail))
    return rows


def check_formats(settings: PicoptSettings) -> tuple[CheckResult, ...]:
    """Report what a run does with each enabled format."""
    ctx = _Context(settings)
    routes = formats_summary(ctx.enabled, ctx.convert_to, ctx.handler_stages)
    rows: list[CheckResult] = []
    by_format = groupby(routes, key=lambda route: route.file_format.format_str)
    for format_str, format_routes in by_format:
        rows.extend(_format_rows(format_str, tuple(format_routes), ctx))
    rows.extend(_convert_to_rows(routes, ctx))
    rows.extend(_opt_in_rows(routes, ctx))
    if (row := _not_enabled_row(ctx)) is not None:
        rows.append(row)
    return tuple(rows)
