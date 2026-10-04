"""Run the checks in report order and print each section as it completes."""

from __future__ import annotations

import sys
from argparse import Namespace
from typing import TYPE_CHECKING, Final, Never

from picopt import plugins as registry
from picopt.doctor.config import SECTION as CONFIG_SECTION
from picopt.doctor.config import check_config
from picopt.doctor.environment import render_environment
from picopt.doctor.formats import SECTION as FORMATS_SECTION
from picopt.doctor.formats import check_formats
from picopt.doctor.packages import SECTION as PACKAGES_SECTION
from picopt.doctor.packages import check_packages
from picopt.doctor.render import (
    render_heading,
    render_rows,
    render_section,
    render_summary,
)
from picopt.doctor.result import FAIL, OFF, WARN, CheckResult, describe
from picopt.doctor.tools import ToolTree
from picopt.log import setup as setup_logging

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from picopt.config.settings import PicoptSettings
    from picopt.plugins.base import Plugin

_PLUGINS_SECTION: Final = "Plugins"
_PATHS_SECTION: Final = "Paths"


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


def _guarded(
    section: str, check: Callable[[], Sequence[CheckResult]]
) -> Sequence[CheckResult]:
    """Run a check; a crash becomes a FAIL row instead of a traceback."""
    try:
        return check()
    except Exception as exc:
        return (CheckResult(section, "check", FAIL, f"crashed: {describe(exc)}"),)


class PicoptDoctor:
    """Check whether a run with these options will work, and say why not."""

    def __init__(self, arguments: Namespace | None = None) -> None:
        """Init results and the tool tree; no arguments checks the defaults."""
        if arguments is None:
            arguments = Namespace(picopt=Namespace(config=None, paths=[], verbose=None))
        self._arguments: Namespace = arguments
        # Read -q from the command line only: a `verbose: 0` in a config
        # file must not hide the report.
        self.problems_only: bool = arguments.picopt.verbose == 0
        self.results: list[CheckResult] = []
        self.tree: ToolTree = ToolTree()
        self._tree_rendered = False

    def _add_section(self, title: str, results: Sequence[CheckResult]) -> None:
        self.results.extend(results)
        render_section(title, results, problems_only=self.problems_only)

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
        """Report failed plugins, then the full tool inventory."""
        plugins, rows = self._discover()
        self.results.extend(rows)
        if self.problems_only:
            # Missing tools that matter show up as Formats rows.
            render_section(_PLUGINS_SECTION, rows, problems_only=True)
            return
        render_heading(_PLUGINS_SECTION)
        render_rows(rows)
        if plugins:
            self.tree.render(plugins)
            self._tree_rendered = True

    def _check_config(self) -> PicoptSettings | None:
        try:
            report = check_config(self._arguments)
        except Exception as exc:
            row = CheckResult(
                CONFIG_SECTION, "check", FAIL, f"crashed: {describe(exc)}"
            )
            self._add_section(CONFIG_SECTION, (row,))
            return None
        self._add_section(CONFIG_SECTION, report.results)
        return report.settings

    def _check_formats(self, settings: PicoptSettings | None) -> None:
        if settings is None:
            rows: Sequence[CheckResult] = (
                CheckResult(
                    FORMATS_SECTION, "not checked", OFF, "config failed to load"
                ),
            )
        else:
            rows = _guarded(FORMATS_SECTION, lambda: check_formats(settings))
        self._add_section(FORMATS_SECTION, rows)

    def _check_paths(self) -> None:
        if paths := self._arguments.picopt.paths:
            detail = f"not analysed yet: {', '.join(paths)}"
            row = CheckResult(_PATHS_SECTION, "paths", WARN, detail)
            self._add_section(_PATHS_SECTION, (row,))

    def exit_code(self) -> int:
        """1 if a run would fail or skip an enabled format, else 0."""
        return int(any(result.status is FAIL for result in self.results))

    def checkup(self) -> int:
        """Print the report. Returns a process exit code."""
        # Header and packages need only metadata, so they print even if
        # plugin discovery crashes below.
        if not self.problems_only:
            render_environment()
        self._add_section(PACKAGES_SECTION, check_packages())
        self._check_plugins()
        # The verdict sections come last, where the terminal leaves them.
        settings = self._check_config()
        self._check_formats(settings)
        self._check_paths()
        extra = self.tree.summary() if self._tree_rendered else ""
        render_summary(self.results, extra)
        return self.exit_code()

    @classmethod
    def doctor_mode(cls, arguments: Namespace | None = None) -> Never:
        """Create the doctor and perform a checkup."""
        # Errors only: the report is the output, and config building must
        # not add its run-time log lines to it.
        setup_logging(0)
        doctor = cls(arguments)
        sys.exit(doctor.checkup())
