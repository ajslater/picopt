"""The doctor's Formats section reports what a run does with each format."""

from pathlib import Path

import pytest

from picopt import PROGRAM_NAME, cli
from picopt import plugins as registry
from picopt.config import PicoptConfig
from picopt.config.handlers import ConfigHandlers
from picopt.plugins.base.tool import ExternalTool, PILSaveTool, ToolStatus
from picopt.plugins.rar import Rar
from picopt.plugins.svg import Svg
from picopt.plugins.webp.const import WEBP_FORMAT_STR
from tests.doctor_util import (
    all_tools,
    find_row,
    isolate_config,
    run_doctor,
    set_available,
)

__all__ = ()

_SVG_TOOLS = tuple(tool for tier in Svg.PIPELINE for tool in tier)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    isolate_config(monkeypatch, tmp_path)


def test_enabled_format_without_tool_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    set_available(monkeypatch, _SVG_TOOLS, available=False)
    code, out = run_doctor(capsys, "-x", "SVG")
    assert code == 1
    row = find_row(out, "FAIL", "SVG")
    assert row == "FAIL SVG no available tool: svgo, bunx_svgo, npx_svgo"
    assert "install:" in out


def test_missing_tool_for_disabled_format_passes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    set_available(monkeypatch, _SVG_TOOLS, available=False)
    code, out = run_doctor(capsys)
    assert code == 0, out
    assert find_row(out, "FAIL", "SVG") is None
    # The tool tree is still a full inventory.
    assert "MISS svgo" in out


def test_pip_only_defaults_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """D1: Pillow fallbacks cover every default format."""
    external = [tool for tool in all_tools() if isinstance(tool, ExternalTool)]
    set_available(monkeypatch, external, available=False)
    code, out = run_doctor(capsys)
    assert code == 0, out
    assert find_row(out, "ok", "PNG") is not None
    # Animated WebP has no Pillow route without -c WEBP: a gap, not a failure.
    row = find_row(out, "WARN", "WEBP animated")
    assert row == "WARN WEBP animated no available tool: webpmux"


def test_probe_error_is_named(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A tool that was found but failed its probe says why, even with -q."""
    unrar = Rar.PIPELINE[0][0]
    status = ToolStatus(name="unrar", available=False, error="cannot extract RAR5")
    monkeypatch.setattr(unrar, "_probed_status", status)
    _, out = run_doctor(capsys, "-q", "-x", "RAR,ZIP", "-c", "ZIP")
    row = find_row(out, "FAIL", "RAR")
    assert row == "FAIL RAR no available tool: unrar (cannot extract RAR5)"


def test_disabled_program_is_named(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    set_available(monkeypatch, _SVG_TOOLS[1:], available=False)
    code, out = run_doctor(capsys, "-x", "SVG", "-D", "svgo")
    assert code == 1
    row = find_row(out, "FAIL", "SVG")
    assert row is not None
    assert "svgo (disabled)" in row


def test_convert_to_without_webp(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    webp_tools = [
        tool
        for tool in all_tools()
        if tool.name in {"cwebp", "img2webp", "gif2webp", "webpmux"}
        or (isinstance(tool, PILSaveTool) and tool.target_format_str == WEBP_FORMAT_STR)
    ]
    set_available(monkeypatch, webp_tools, available=False)
    _, out = run_doctor(capsys, "-c", "WEBP")
    row = find_row(out, "WARN", "-c WEBP")
    assert row == "WARN -c WEBP no enabled format converts to WEBP"


def test_unpackable_archive_needs_convert(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run_doctor(capsys, "-x", "RAR")
    assert code == 1
    assert find_row(out, "FAIL", "RAR") == "FAIL RAR read only: add -c ZIP"


def test_convert_target_must_be_enabled(capsys: pytest.CaptureFixture[str]) -> None:
    _, out = run_doctor(capsys, "-x", "RAR", "-c", "ZIP")
    assert find_row(out, "FAIL", "RAR") == "FAIL RAR -c ZIP needs -x ZIP"


def test_archive_needs_its_reader_to_convert(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Converting RAR to ZIP still needs unrar to unpack it."""
    set_available(monkeypatch, (Rar.PIPELINE[0][0],), available=False)
    code, out = run_doctor(capsys, "-x", "RAR,ZIP", "-c", "ZIP")
    assert code == 1
    assert find_row(out, "FAIL", "RAR") == "FAIL RAR no available tool: unrar"


def test_convert_only_format(capsys: pytest.CaptureFixture[str]) -> None:
    _, out = run_doctor(capsys, "-x", "BMP")
    row = find_row(out, "FAIL", "BMP")
    assert row == "FAIL BMP converts only: add -c JXL or WEBP or PNG"


def test_opt_in_flag_without_target(capsys: pytest.CaptureFixture[str]) -> None:
    _, out = run_doctor(capsys, "--convert-jpeg-to-jxl")
    row = find_row(out, "WARN", "--convert-jpeg-to-jxl")
    assert row == "WARN --convert-jpeg-to-jxl has no effect without -c JXL"


def test_banner_and_doctor_agree(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    args = ("-x", "RAR,CBR,BMP,ZIP", "-c", "ZIP,PNG")
    banner: dict[str, set[str]] = {}

    def _capture(
        _verbose: int, handled: set[str], converts: dict[str, set[str]]
    ) -> None:
        banner["handled"] = handled
        banner["converted"] = {src for srcs in converts.values() for src in srcs}

    monkeypatch.setattr(ConfigHandlers, "_print_formats_config", staticmethod(_capture))
    PicoptConfig().get_config(cli.get_arguments((PROGRAM_NAME, *args, ".")))
    _, out = run_doctor(capsys, *args)
    format_strs = set(registry.all_format_strs())
    doctor_ok = {
        words[1]
        for line in out.splitlines()
        if (words := line.split())[:1] == ["ok"] and words[1] in format_strs
    }
    assert banner["handled"] == doctor_ok
    assert {"BMP", "RAR"} <= banner["converted"]
    for format_str in banner["converted"]:
        row = find_row(out, "ok", format_str)
        assert row is not None
        assert " to " in row
