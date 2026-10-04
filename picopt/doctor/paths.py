"""
Per-path analysis: each target's ``.picopt.yaml`` files and its stamps.

The stamp rows come from :meth:`Grove.inspect_trees`, which builds the same
config a run loads with, through treestamps' read-only ``inspect()``.
Nothing here writes: not a stamp file, not a config. Only a missing target
fails the report; a discarded stamp file costs time, not correctness.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Final

from confuse import YamlSource
from confuse.exceptions import ConfigError
from humanize import naturaltime

from picopt.config import DIR_CONFIG_FILENAME, config_keys
from picopt.config.consts import RUN_SCOPED_KEYS
from picopt.config.dirconfig import DirConfig
from picopt.doctor.config import format_value, unknown_key_rows
from picopt.doctor.result import (
    FAIL,
    INFO,
    OFF,
    OK,
    WARN,
    CheckResult,
    DoctorStatus,
    describe,
    display_path,
    one_line,
    plural,
)

if TYPE_CHECKING:
    from argparse import Namespace
    from collections.abc import Iterator

    from treestamps import StampFileReport, TreestampsReport

    from picopt.config import PicoptConfig
    from picopt.config.settings import PicoptSettings

# Honored in a tree root's .picopt.yaml, but nowhere below it.
_ROOT_ONLY_KEY: Final = "timestamps"
# Compared between the run and a tree root: settings the user can set.
_TREE_SKIP_KEYS: Final = frozenset({"paths"})


class _PathCheck:
    """The rows for one command line target."""

    def __init__(
        self,
        path_str: str,
        settings: PicoptSettings,
        dirconfig: DirConfig,
    ) -> None:
        self.section: str = _section(path_str)
        self.path: Path = Path(path_str)
        self.settings: PicoptSettings = settings
        self.dirconfig: DirConfig = dirconfig
        # The same rule as Treestamps.get_dir, without importing treestamps.
        self.root_dir: Path = self.path if self.path.is_dir() else self.path.parent
        self.rows: list[CheckResult] = []

    def _row(
        self, name: str, status: DoctorStatus, detail: str = "", fix: str = ""
    ) -> None:
        self.rows.append(CheckResult(self.section, name, status, detail, fix))

    # ── .picopt.yaml lint ─────────────────────────────────────────────

    def _readable(self, config_file: Path) -> bool:
        # The run reads a symlinked config file only when following symlinks.
        return config_file.is_file() and (
            self.settings.symlinks or not config_file.is_symlink()
        )

    def _lint(self, config_file: Path, *, is_root: bool) -> None:
        """WARN for what the run ignores in one .picopt.yaml."""
        label = display_path(config_file)
        try:
            source = YamlSource(str(config_file))
        except (ConfigError, TypeError) as exc:
            # The run logs the same failure and falls back to the run's
            # settings for the directory.
            self._row("unreadable", WARN, f"{label}: {one_line(str(exc))}")
            return
        self.rows.extend(unknown_key_rows(source, label, config_keys(), self.section))
        section = source.get("picopt")
        if not isinstance(section, dict):
            return
        for key in sorted(RUN_SCOPED_KEYS & set(map(str, section))):
            if key == _ROOT_ONLY_KEY:
                if is_root:
                    continue
                detail = f"{key} ({label}): honoured at a tree root only"
            else:
                detail = f"{key} ({label}): no per-directory effect"
            self._row("run-scoped key", WARN, detail)

    def _sub_dir_configs(self) -> Iterator[Path]:
        """Every .picopt.yaml below the root that a recursive run reads."""
        # Ignore patterns aren't applied: a row for an ignored directory is
        # a harmless extra.
        for dir_path, _, file_names in os.walk(
            self.root_dir, followlinks=self.settings.symlinks
        ):
            path = Path(dir_path)
            if path != self.root_dir and DIR_CONFIG_FILENAME in file_names:
                config_file = path / DIR_CONFIG_FILENAME
                if self._readable(config_file):
                    yield config_file

    def _check_configs(self, tree_settings: PicoptSettings) -> None:
        root_config = self.root_dir / DIR_CONFIG_FILENAME
        if self._readable(root_config):
            self._row("root config", OK, display_path(root_config))
            self._lint(root_config, is_root=True)
        if tree_settings.recurse and self.path.is_dir():
            for config_file in sorted(self._sub_dir_configs()):
                self._lint(config_file, is_root=False)

    # ── Tree settings ─────────────────────────────────────────────────

    def _check_tree_settings(self, tree_settings: PicoptSettings) -> None:
        """INFO for each setting the root's .picopt.yaml changes."""
        label = display_path(self.root_dir / DIR_CONFIG_FILENAME)
        for key in sorted(config_keys() - _TREE_SKIP_KEYS):
            value = getattr(tree_settings, key, None)
            if value != getattr(self.settings, key, None):
                detail = f"{format_value(value)}  from {label}"
                self._row(key, INFO, detail)

    # ── Stamps ────────────────────────────────────────────────────────

    def _stamps_off(self, tree_settings: PicoptSettings) -> None:
        detail = "timestamps off for this tree"
        root_config = self.root_dir / DIR_CONFIG_FILENAME
        if self.settings.timestamps and not tree_settings.timestamps:
            detail += f": turned off by {display_path(root_config)}"
        self._row("stamps", OFF, detail)

    def _snapshot_row(self, snapshot: StampFileReport) -> None:
        labels = ", ".join(snapshot.diff_labels)
        if snapshot.error:
            error = one_line(snapshot.error)
            detail = f"unreadable: {error}; it will be discarded and rewritten"
            self._row("stamps", WARN, detail)
        elif not snapshot.exists or snapshot.mtime is None:
            self._row("stamps", INFO, "no stamps yet")
        elif snapshot.would_discard:
            detail = (
                f"will be discarded: config changed for {labels}; "
                "the run re-optimizes the whole tree"
            )
            self._row("stamps", WARN, detail)
        else:
            entries = plural(snapshot.entry_count, "entry", "entries")
            age = naturaltime(time.time() - snapshot.mtime)
            self._row("stamps", OK, f"{entries}, written {age}")
            if snapshot.diff_keys:
                detail = f"config differs for {labels}, but -N skips the check"
                self._row("stamps", WARN, detail)

    def _wal_row(self, wal: StampFileReport) -> None:
        if not wal.exists:
            return
        if wal.error or wal.would_discard:
            reason = one_line(wal.error or "") or (
                f"config changed for {', '.join(wal.diff_labels)}"
            )
            detail = f"an interrupted run's WAL will be discarded: {reason}"
            self._row("stamps WAL", WARN, detail)
            return
        entries = plural(wal.entry_count, "entry", "entries")
        detail = f"unflushed WAL with {entries} from an interrupted run; merged on the next run"
        self._row("stamps WAL", INFO, detail)

    def _children_rows(self, children: tuple[StampFileReport, ...]) -> None:
        if not children:
            return
        count = plural(len(children), "file")
        self._row("child stamps", INFO, f"{count} the next run absorbs")
        for child in children:
            if child.error or child.would_discard:
                reason = one_line(child.error or "") or (
                    f"config changed for {', '.join(child.diff_labels)}"
                )
                detail = f"{display_path(child.path)} will be discarded: {reason}"
                self._row("child stamps", WARN, detail)

    def _check_stamps(self, tree_settings: PicoptSettings) -> None:
        try:
            from picopt.walk.grove import Grove
        except ImportError as exc:
            self._row("stamps", FAIL, f"timestamps unavailable: {describe(exc)}")
            return
        reports = Grove.inspect_trees((self.path,), self.dirconfig, self.settings)
        report: TreestampsReport | None = next(iter(reports.values()), None)
        if report is None:
            self._stamps_off(tree_settings)
            return
        self._snapshot_row(report.snapshot)
        self._wal_row(report.wal)
        self._children_rows(report.children or ())

    # ── Run ───────────────────────────────────────────────────────────

    def check(self) -> list[CheckResult]:
        """Return this target's rows."""
        if not self.path.exists():
            # The run raises before walking anything.
            self._row("missing", FAIL, "does not exist")
            return self.rows
        if self.path.is_symlink() and not self.settings.symlinks:
            self._row("symlink", OFF, "skipped: -S excludes symlinked targets")
            return self.rows
        self._row("tree root", INFO, display_path(self.root_dir.absolute()))
        tree_settings = self.dirconfig.get_tree_settings(self.path)
        self._check_configs(tree_settings)
        self._check_tree_settings(tree_settings)
        self._check_stamps(tree_settings)
        return self.rows


def _section(path_str: str) -> str:
    return f"Path {path_str}"


def check_paths(
    arguments: Namespace, picopt_config: PicoptConfig, settings: PicoptSettings
) -> list[tuple[str, list[CheckResult]]]:
    """Return a section of rows per command line target."""
    dirconfig = DirConfig(picopt_config, arguments, settings)
    sections = []
    for path_str in arguments.picopt.paths:
        try:
            rows = _PathCheck(path_str, settings, dirconfig).check()
        except Exception as exc:
            detail = f"crashed: {describe(exc)}"
            rows = [CheckResult(_section(path_str), "check", FAIL, detail)]
        sections.append((_section(path_str), rows))
    return sections


def unchecked_paths(arguments: Namespace) -> list[tuple[str, list[CheckResult]]]:
    """Without settings, report only whether each target exists."""
    sections = []
    for path_str in arguments.picopt.paths:
        section = _section(path_str)
        if Path(path_str).exists():
            row = CheckResult(section, "not checked", OFF, "config failed to load")
        else:
            row = CheckResult(section, "missing", FAIL, "does not exist")
        sections.append((section, [row]))
    return sections
