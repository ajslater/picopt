"""
``picopt doctor`` — report which optimization tools are available.

Walks every plugin's handlers and probes their PIPELINE tools, printing a
tree of plugin -> handler -> tier ->  tool with availability, version, and
path. Optional tools that are missing are reported separately from
required ones at the bottom.

Probing CWebPTool here also surfaces (via the WebPLossless.IS_MODERN_CWEBP
side effect) whether old or new cwebp behavior is in effect.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from rich.markup import escape

from picopt import plugins as registry
from picopt.log import console
from picopt.plugins.webp import CWebPTool

if TYPE_CHECKING:
    from collections.abc import Sequence


class PicoptDoctor:
    """Picopt doctor."""

    def __init__(self) -> None:
        """Init totals."""
        self.total_required = 0
        self.missing_required = 0
        self.missing_optional = 0

    def _checkup_tool_get_tier_and_name(
        self, status, tier_idx: int, tool
    ) -> tuple[list[str], bool]:
        tier_has_available = False
        if status.required:
            self.total_required += 1
        if status.available:
            tier_has_available = True
            prefix = "ok  "
            tier_color = "green"
        else:
            prefix = "MISS"
            if status.required:
                self.missing_required += 1
                tier_color = "red"
            else:
                self.missing_optional += 1
                tier_color = "cyan"
        name = tool.name or type(tool).__name__
        return [
            f"[{tier_color}]    tier {tier_idx} {prefix} {name}[/{tier_color}]"
        ], tier_has_available

    def _checkup_tool(self, tier_idx, tool) -> bool:
        status = tool.probe()
        bits, tier_has_available = self._checkup_tool_get_tier_and_name(
            status, tier_idx, tool
        )

        if status.version:
            bits.append(f"[bold black]{escape(status.version)}[/bold black]")
        if status.path and status.path != "<builtin>":
            bits.append(f"[dim white]\\[{escape(status.path)}][/dim white]")

        if not status.available and status.error:
            bits.extend(["-", f"[red]{escape(status.error)}[/red]"])
        elif isinstance(tool, CWebPTool):
            # Probe-side-effect on WebPLossless: announce the cwebp generation.
            flag = "modern" if CWebPTool.IS_MODERN_CWEBP else "legacy"
            flag_color = "green" if CWebPTool.IS_MODERN_CWEBP else "cyan"
            bits.append(f"([{flag_color}]{flag}[/{flag_color}])")

        console.print(" ".join(bits))
        return tier_has_available

    def _checkup_handler_pipeline_tier(self, tier_idx: int, tier) -> None:
        tier_has_available = False
        for tool in tier:
            tier_has_available |= self._checkup_tool(tier_idx, tool)
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
        available_tools = self.total_required - self.missing_required
        required_color = "red" if self.missing_required else "green"
        optional_color = "cyan" if self.missing_optional else "green"

        console.print(
            "Summary: "
            f"[{required_color}]"
            f"{available_tools}/{self.total_required} required tools available"
            f"[/{required_color}], "
            f"[{required_color}]{self.missing_required} missing required"
            f"[/{required_color}], "
            f"[{optional_color}]{self.missing_optional} missing optional"
            f"[/{optional_color}]."
        )

    def checkup(self) -> int:
        """Run the doctor command. Returns a process exit code."""
        console.print(
            "[yellow]Plugins[/yellow]\n"
            "  [bold cyan]Formats[/bold cyan]\n"
            "    [cyan]Tools[/cyan]"
        )
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
