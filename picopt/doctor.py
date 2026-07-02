"""
``picopt doctor`` — report which optimization tools are available.

Walks every plugin's handlers and probes their PIPELINE tools, printing a
tree of plugin -> handler -> tier ->  tool with availability, version, and
path. Optional tools that are missing are reported separately from
required ones at the bottom.

When a tool is missing, the doctor shows a platform-appropriate install
command (brew on macOS, apt on Debian/Ubuntu, dnf on Fedora/RHEL).

Probing CWebPTool here also surfaces (via the WebPLossless.IS_MODERN_CWEBP
side effect) whether old or new cwebp behavior is in effect.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from rich.markup import escape

from picopt import plugins as registry
from picopt.log import console
from picopt.plugins.webp import CWebPTool

if TYPE_CHECKING:
    from collections.abc import Sequence

# ── Platform detection ────────────────────────────────────────────────

_BREW = "brew"
_APT = "apt"
_DNF = "dnf"


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
                _APT: "apt install unrar",
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


def _install_hint(tool_name: str, pkg_manager: str) -> str:
    hints = _INSTALL_HINTS.get(tool_name, {})
    return hints.get(pkg_manager, "")


# ── Doctor ────────────────────────────────────────────────────────────


class PicoptDoctor:
    """Picopt doctor."""

    def __init__(self) -> None:
        """Init totals."""
        self.total_required = 0
        self.missing_required = 0
        self.missing_optional = 0
        self._pkg_manager: str = _detect_pkg_manager()

    def _checkup_tool_get_tier_and_name(
        self, status, tier_idx: int, tool
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
        name = tool.name or type(tool).__name__
        return [
            f"[{tier_color}]    tier {tier_idx} {prefix} {name}[/{tier_color}]"
        ], tier_has_available

    @staticmethod
    def _checkup_tool_detail_bits(status, tool) -> list[str]:
        bits: list[str] = []
        if status.version:
            bits.append(f"[bold black]{escape(status.version)}[/bold black]")
        if status.path and status.path != "<builtin>":
            bits.append(f"[dim white]\\[{escape(status.path)}][/dim white]")
        if not status.available and status.error:
            bits.extend(["-", f"[red]{escape(status.error)}[/red]"])
        elif isinstance(tool, CWebPTool):
            flag = "modern" if CWebPTool.IS_MODERN_CWEBP else "legacy"
            flag_color = "green" if CWebPTool.IS_MODERN_CWEBP else "cyan"
            bits.append(f"([{flag_color}]{flag}[/{flag_color}])")
        return bits

    def _checkup_tool_print_hint(self, status, tool) -> None:
        if status.available:
            return
        tool_name = tool.name or type(tool).__name__
        hint = _install_hint(tool_name, self._pkg_manager)
        if hint:
            console.print(f"[dim]             install: {escape(hint)}[/dim]")

    def _checkup_tool(self, tier_idx, tool) -> bool:
        status = tool.probe()
        bits, tier_has_available = self._checkup_tool_get_tier_and_name(
            status, tier_idx, tool
        )
        bits.extend(self._checkup_tool_detail_bits(status, tool))
        console.print(" ".join(bits))
        self._checkup_tool_print_hint(status, tool)
        return tier_has_available

    def _checkup_handler_pipeline_tier(self, tier_idx: int, tier) -> None:
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

    def _checkup_handler(self, handler_cls) -> None:
        console.print(f"[bold cyan]  {handler_cls.__name__}[/bold cyan]")
        if not handler_cls.PIPELINE:
            console.print("    (no external pipeline — always available)")
            return
        for tier_idx, tier in enumerate(handler_cls.PIPELINE):
            self._checkup_handler_pipeline_tier(tier_idx, tier)

    def _checkup_plugin(self, plugin) -> None:
        if plugin.name == "PIL_CONVERTIBLE":
            return
        console.print(f"[yellow]{plugin.name}[/yellow]")
        for handler_cls in plugin.handlers:
            self._checkup_handler(handler_cls)

    def _checkup_report(self) -> None:
        available_tiers = self.total_required - self.missing_required
        required_color = "red" if self.missing_required else "green"
        optional_color = "cyan" if self.missing_optional else "green"

        summary = (
            "Summary: "
            f"[{required_color}]"
            f"{available_tiers}/{self.total_required} required tool tiers available"
            f"[/{required_color}], "
            f"[{required_color}]{self.missing_required} missing required"
            f"[/{required_color}], "
            f"[{optional_color}]{self.missing_optional} missing optional tools"
            f"[/{optional_color}]."
        )
        console.print(summary)

    def checkup(self) -> int:
        """Run the doctor command. Returns a process exit code."""
        header = (
            "[yellow]Plugins[/yellow]\n"
            "  [bold cyan]Formats[/bold cyan]\n"
            "    [cyan]Tools[/cyan]"
        )
        console.print(header)
        for plugin in sorted(registry.iter_plugins(), key=lambda p: p.name):
            self._checkup_plugin(plugin)
            console.print("")

        self._checkup_report()
        return min(self.missing_required, 1)

    @classmethod
    def doctor_mode(cls) -> None:
        """Create the doctor and perform a checkup."""
        doctor = cls()
        sys.exit(doctor.checkup())

    @classmethod
    def parse_cli(cls: type[Any], args: Sequence[str] | None = None) -> None:
        """Parse the cli to to enter doctor mode or return."""
        argv = args if args is not None else tuple(sys.argv)
        if len(argv) >= 2 and argv[1] == "doctor":  # noqa: PLR2004
            cls.doctor_mode()


if __name__ == "__main__":
    PicoptDoctor.doctor_mode()
