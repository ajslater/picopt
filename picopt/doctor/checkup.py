"""Run the checks in report order and print each section as it completes."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Final, Never

from picopt import plugins as registry
from picopt.doctor.environment import render_environment
from picopt.doctor.packages import SECTION as PACKAGES_SECTION
from picopt.doctor.packages import check_packages
from picopt.doctor.render import (
    render_heading,
    render_rows,
    render_section,
    render_summary,
)
from picopt.doctor.result import FAIL, CheckResult, describe
from picopt.doctor.tools import ToolTree

if TYPE_CHECKING:
    from collections.abc import Sequence

    from picopt.plugins.base import Plugin

_PLUGINS_SECTION: Final = "Plugins"


def _failed_plugin_rows() -> list[CheckResult]:
    return [
        CheckResult(
            _PLUGINS_SECTION,
            failure.module,
            FAIL,
            f"failed to load: {describe(failure.error)}",
        )
        for failure in registry.failed_plugins()
    ]


class PicoptDoctor:
    """Check whether picopt can run here, and say why not."""

    def __init__(self) -> None:
        """Init results and the tool tree."""
        self.results: list[CheckResult] = []
        self.tree: ToolTree = ToolTree()
        self._tree_rendered = False

    def _add_section(self, title: str, results: Sequence[CheckResult]) -> None:
        self.results.extend(results)
        render_section(title, results, problems_only=False)

    def _discover(self) -> tuple[Sequence[Plugin], list[CheckResult]]:
        """Load plugins; a crash D6 doesn't isolate becomes a FAIL row."""
        try:
            plugins = tuple(registry.iter_plugins())
            rows = _failed_plugin_rows()
        except Exception as exc:
            detail = f"plugin discovery failed: {describe(exc)}"
            return (), [CheckResult(_PLUGINS_SECTION, "discovery", FAIL, detail)]
        return plugins, rows

    def _check_plugins(self) -> None:
        plugins, rows = self._discover()
        self.results.extend(rows)
        render_heading(_PLUGINS_SECTION)
        render_rows(rows)
        if plugins:
            self.tree.render(plugins)
            self._tree_rendered = True

    def exit_code(self) -> int:
        """1 if any row failed or a required tool tier is missing, else 0."""
        failed = any(result.status is FAIL for result in self.results)
        return int(failed or bool(self.tree.missing_required))

    def checkup(self) -> int:
        """Print the report. Returns a process exit code."""
        # Header and packages need only metadata, so they print even if
        # plugin discovery crashes below.
        render_environment()
        self._add_section(PACKAGES_SECTION, check_packages())
        self._check_plugins()
        extra = self.tree.summary() if self._tree_rendered else ""
        render_summary(self.results, extra)
        return self.exit_code()

    @classmethod
    def doctor_mode(cls) -> Never:
        """Create the doctor and perform a checkup."""
        doctor = cls()
        sys.exit(doctor.checkup())
