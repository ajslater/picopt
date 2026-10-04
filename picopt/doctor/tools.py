"""
The tool inventory: every plugin's handlers and their PIPELINE tools.

Prints a tree of plugin -> handler -> tier -> tool with availability,
version, and path. It is an inventory, not a verdict: a missing tool matters
only when an enabled format needs it, which the Formats section decides.

When a tool is missing, the tree shows a platform-appropriate install
command (brew on macOS, apt on Debian/Ubuntu, dnf on Fedora/RHEL).

Probing CWebPTool also surfaces (via the probed instance's ``is_modern``
flag) whether old or new cwebp behavior is in effect.
"""

from __future__ import annotations

import sys
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from rich.markup import escape

from picopt.log import console
from picopt.plugins.webp import CWebPTool

if TYPE_CHECKING:
    from collections.abc import Iterable

    from picopt.plugins.base import Handler, Plugin, Tool, ToolStatus

# ── Platform detection ────────────────────────────────────────────────

_BREW = "brew"
_APT = "apt"
_DNF = "dnf"


@cache
def _detect_pkg_manager() -> str:
    if sys.platform == "darwin":
        return _BREW
    if sys.platform == "linux":
        try:
            info = Path("/etc/os-release").read_text()
        except OSError:
            return ""
        lower = info.lower()
        if "debian" in lower or "ubuntu" in lower:
            return _APT
        if "fedora" in lower or "rhel" in lower or "centos" in lower:
            return _DNF
    return ""


# ── Install hints keyed by (tool name, package manager) ──────────────
# Tools from the same upstream package share the same hint.

_WEBP_HINTS: MappingProxyType[str, str] = MappingProxyType(
    {
        _BREW: "brew install webp",
        _APT: "apt install webp",
        _DNF: "dnf install libwebp-tools",
    }
)

_INSTALL_HINTS: MappingProxyType[str, MappingProxyType[str, str]] = MappingProxyType(
    {
        "gifsicle": MappingProxyType(
            {
                _BREW: "brew install gifsicle",
                _APT: "apt install gifsicle",
                _DNF: "dnf install gifsicle",
            }
        ),
        "cwebp": _WEBP_HINTS,
        "gif2webp": _WEBP_HINTS,
        "img2webp": _WEBP_HINTS,
        "webpmux": _WEBP_HINTS,
        "unrar": MappingProxyType(
            {
                _BREW: "brew install rar",
                # RARLAB's unrar, not the unrar-free package.
                _APT: "apt install unrar (Debian non-free or Ubuntu multiverse)",
                _DNF: "dnf install unrar",
            }
        ),
        "pngout": MappingProxyType({_BREW: "brew install jonof/kenutils/pngout"}),
        "svgo": MappingProxyType(
            {
                _BREW: "brew install svgo",
                _APT: "npm install -g svgo",
                _DNF: "npm install -g svgo",
            }
        ),
        "npx_svgo": MappingProxyType(
            {
                _BREW: "npm install -g svgo",
                _APT: "npm install -g svgo",
                _DNF: "npm install -g svgo",
            }
        ),
        "bunx_svgo": MappingProxyType(
            {
                _BREW: "bun install -g svgo",
                _APT: "bun install -g svgo",
                _DNF: "bun install -g svgo",
            }
        ),
    }
)


def tool_name(tool: Tool) -> str:
    """Return the name a tool is shown, disabled and hinted by."""
    return tool.name or type(tool).__name__


def install_hint(name: str) -> str:
    """Return this platform's install command for a tool, or ""."""
    hints = _INSTALL_HINTS.get(name, {})
    return hints.get(_detect_pkg_manager(), "")


# ── Tree ──────────────────────────────────────────────────────────────


class ToolTree:
    """Print the tool inventory and count required tiers."""

    def __init__(self) -> None:
        """Init totals."""
        self.total_required = 0
        self.missing_required = 0
        self.missing_optional = 0

    def _checkup_tool_get_tier_and_name(
        self, status: ToolStatus, tier_idx: int, tool: Tool
    ) -> tuple[list[str], bool]:
        tier_has_available = False
        if status.available:
            tier_has_available = True
            prefix = "ok  "
            tier_color = "green"
        else:
            prefix = "MISS"
            if status.required:
                tier_color = "red"
            else:
                self.missing_optional += 1
                tier_color = "cyan"
        name = tool_name(tool)
        return [
            f"[{tier_color}]    tier {tier_idx} {prefix} {name}[/{tier_color}]"
        ], tier_has_available

    @staticmethod
    def _checkup_tool_detail_bits(status: ToolStatus, tool: Tool) -> list[str]:
        bits: list[str] = []
        if status.version:
            bits.append(f"[bold black]{escape(status.version)}[/bold black]")
        if status.path and status.path != "<builtin>":
            bits.append(f"[dim white]\\[{escape(status.path)}][/dim white]")
        if not status.available and status.error:
            bits.extend(["-", f"[red]{escape(status.error)}[/red]"])
        elif status.detail:
            bits.append(f"([green]{escape(status.detail)}[/green])")
        elif isinstance(tool, CWebPTool):
            flag = "modern" if tool.is_modern else "legacy"
            flag_color = "green" if tool.is_modern else "cyan"
            bits.append(f"([{flag_color}]{flag}[/{flag_color}])")
        return bits

    @staticmethod
    def _checkup_tool_print_hint(status: ToolStatus, tool: Tool) -> None:
        if status.available:
            return
        if hint := install_hint(tool_name(tool)):
            console.print(f"[dim]             install: {escape(hint)}[/dim]")

    def _checkup_tool(self, tier_idx: int, tool: Tool) -> bool:
        status = tool.probe()
        bits, tier_has_available = self._checkup_tool_get_tier_and_name(
            status, tier_idx, tool
        )
        bits.extend(self._checkup_tool_detail_bits(status, tool))
        console.print(" ".join(bits))
        self._checkup_tool_print_hint(status, tool)
        return tier_has_available

    def _checkup_handler_pipeline_tier(
        self, tier_idx: int, tier: tuple[Tool, ...]
    ) -> None:
        tier_has_available = False
        for tool in tier:
            tier_has_available |= self._checkup_tool(tier_idx, tool)
        # Tools within a tier are ALTERNATIVES: the tier is healthy when
        # any one of them is available. Count requirements per tier, not
        # per tool, or healthy installs report missing-required tools.
        if any(tool.required for tool in tier):
            self.total_required += 1
            if not tier_has_available:
                self.missing_required += 1
        if not tier_has_available:
            console.print(
                f"[yellow]    !!! tier {tier_idx} has no available tool[/yellow]"
            )

    def _checkup_handler(self, handler_cls: type[Handler]) -> None:
        console.print(f"[bold cyan]  {handler_cls.__name__}[/bold cyan]")
        if not handler_cls.PIPELINE:
            console.print("    (no external pipeline — always available)")
            return
        for tier_idx, tier in enumerate(handler_cls.PIPELINE):
            self._checkup_handler_pipeline_tier(tier_idx, tier)

    def _checkup_plugin(self, plugin: Plugin) -> None:
        if plugin.name == "PIL_CONVERTIBLE":
            return
        console.print(f"[yellow]{plugin.name}[/yellow]")
        for handler_cls in plugin.handlers:
            self._checkup_handler(handler_cls)

    def render(self, plugins: Iterable[Plugin]) -> None:
        """Print the tree for these plugins."""
        header = (
            "  [yellow]Plugin[/yellow]\n"
            "    [bold cyan]Handler[/bold cyan]\n"
            "      [cyan]Tools[/cyan]"
        )
        console.print(header)
        for plugin in sorted(plugins, key=lambda p: p.name):
            self._checkup_plugin(plugin)
            console.print("")

    def summary(self) -> str:
        """Tier counts for the summary line."""
        available = self.total_required - self.missing_required
        return f"{available}/{self.total_required} required tool tiers available"
