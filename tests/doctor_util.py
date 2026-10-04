"""Helpers for the doctor tests."""

import os
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest

from picopt import PROGRAM_NAME, cli
from picopt import plugins as registry
from picopt.plugins.base.tool import Tool, ToolStatus

__all__ = (
    "all_tools",
    "find_row",
    "isolate_config",
    "run_doctor",
    "set_available",
)


def isolate_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point confuse at an empty config dir, scrub picopt env vars, widen."""
    for key in list(os.environ):
        if key.startswith("PICOPT"):
            monkeypatch.delenv(key, raising=False)
    config_dir = tmp_path / "config"
    monkeypatch.setenv("PICOPTDIR", str(config_dir))
    # Wide enough that no report row wraps.
    monkeypatch.setenv("COLUMNS", "300")
    return config_dir


def run_doctor(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str]:
    """Run ``picopt doctor ARGS``; return its exit code and output."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main((PROGRAM_NAME, "doctor", *args))
    code = exc_info.value.code
    assert isinstance(code, int)
    return code, capsys.readouterr().out


def find_row(out: str, status: str, name: str) -> str | None:
    """
    Return the report row with this status tag and name, whitespace collapsed.

    INFO rows have no tag: pass "" to find them by name alone.
    """
    prefix = f"{status} {name} " if status else f"{name} "
    for line in out.splitlines():
        row = " ".join(line.split()) + " "
        if row.startswith(prefix):
            return row.strip()
    return None


def all_tools() -> Iterator[Tool]:
    """Every distinct tool instance; handlers share pipelines."""
    yield from dict.fromkeys(
        tool
        for handler_cls in registry.all_handlers()
        for tier in handler_cls.PIPELINE
        for tool in tier
    )


def set_available(
    monkeypatch: pytest.MonkeyPatch, tools: Iterable[Tool], *, available: bool
) -> None:
    """Fix tools' probe results; monkeypatch restores the real ones."""
    for tool in tools:
        status = ToolStatus(
            name=tool.name,
            available=available,
            error="" if available else f"{tool.name} not found in PATH",
            required=tool.required,
        )
        monkeypatch.setattr(tool, "_probed_status", status)
