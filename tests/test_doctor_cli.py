"""``picopt doctor`` dispatch, options, exit codes and resilience."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from picopt import PROGRAM_NAME, cli
from picopt import plugins as registry
from picopt.doctor.environment import environment_lines
from picopt.plugins.svg import Svg
from tests.doctor_util import (
    all_tools,
    find_row,
    isolate_config,
    run_doctor,
    set_available,
)

__all__ = ()

_HEALTHY_SUMMARY = "Summary: no problems, 0 warnings."


@pytest.fixture(autouse=True)
def config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    return isolate_config(monkeypatch, tmp_path)


@pytest.fixture
def every_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the machine healthy whatever is installed."""
    set_available(monkeypatch, all_tools(), available=True)


def test_healthy_doctor_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run_doctor(capsys)
    assert code == 0, out
    for heading in ("Python packages", "Plugins", "Config", "Formats", "Summary:"):
        assert heading in out


def test_options_are_honoured(capsys: pytest.CaptureFixture[str]) -> None:
    _, out = run_doctor(capsys, "-x", "SVG")
    assert find_row(out, "ok", "SVG") or find_row(out, "FAIL", "SVG")
    not_enabled = find_row(out, "off", "not enabled")
    assert not_enabled is not None
    assert "SVG" not in not_enabled.split(maxsplit=3)[3]


def test_write_flags_warn_and_write_nothing(
    config_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "written.yaml"
    _, out = run_doctor(capsys, "-w", "-W", "--write-config-file", str(target), "-r")
    for flag in ("-w", "-W", "--write-config-file"):
        assert (
            find_row(out, "WARN", flag)
            == f"WARN {flag} ignored: the doctor never writes"
        )
    assert not (config_dir / "config.yaml").exists()
    assert not target.exists()


def test_bad_option_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    code, _ = run_doctor(capsys, "--bogus")
    assert code == 2  # noqa: PLR2004


def test_dot_slash_doctor_is_a_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "doctor").mkdir()
    monkeypatch.chdir(tmp_path)
    # Optimizes the (empty) directory instead of entering doctor mode.
    cli.main((PROGRAM_NAME, "-q", "./doctor"))


def test_discovery_crash_is_a_fail_row(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _crash():
        reason = "boom"
        raise ValueError(reason)

    monkeypatch.setattr(registry, "iter_plugins", _crash)
    code, out = run_doctor(capsys)
    assert code == 1
    row = find_row(out, "FAIL", "discovery")
    assert row == "FAIL discovery plugin discovery failed: ValueError: boom"
    assert "Python packages" in out
    assert "Summary:" in out


def test_environment_names_env_vars_without_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PICOPT_PICOPT__IGNORE", "secret-pattern")
    lines = "\n".join(environment_lines())
    assert "PICOPT_PICOPT__IGNORE" in lines
    assert "secret-pattern" not in lines
    assert lines.startswith(f"{PROGRAM_NAME} ")
    assert "Pillow " in lines


@pytest.mark.usefixtures("every_tool")
class TestProblemsOnly:
    """-q prints only WARN and FAIL rows, with their fixes, and the summary."""

    def test_healthy_prints_only_summary(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code, out = run_doctor(capsys, "-q")
        assert code == 0
        assert out.strip() == _HEALTHY_SUMMARY

    def test_failure_prints_its_section_only(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        svg_tools = [tool for tier in Svg.PIPELINE for tool in tier]
        set_available(monkeypatch, svg_tools, available=False)
        code, out = run_doctor(capsys, "-q", "-x", "SVG")
        assert code == 1
        lines = [" ".join(line.split()) for line in out.strip().splitlines()]
        assert lines[0] == "Formats"
        assert lines[1] == "FAIL SVG no available tool: svgo, bunx_svgo, npx_svgo"
        assert lines[-1] == "Summary: 1 problem, 0 warnings."
        # Only the install hints sit between the row and the summary.
        assert all(line.startswith("install:") for line in lines[2:-1])

    def test_doctor_warnings_survive(self, capsys: pytest.CaptureFixture[str]) -> None:
        code, out = run_doctor(capsys, "-q", "-w")
        assert code == 0
        assert find_row(out, "WARN", "-w") is not None
        assert out.strip().endswith("Summary: no problems, 1 warning.")

    def test_config_verbose_zero_keeps_full_report(
        self, config_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("picopt:\n  verbose: 0\n")
        _, out = run_doctor(capsys)
        assert "Python packages" in out
        assert find_row(out, "", "verbose") is not None


def _loads_treestamps(code: str, tmp_path: Path) -> bool:
    """Run code in a fresh interpreter; report whether treestamps loaded."""
    script = f"import sys\n{code}\nprint('treestamps' in sys.modules)"
    env = {**os.environ, "PICOPTDIR": str(tmp_path / "config")}
    result = subprocess.run(  # noqa: S603
        (sys.executable, "-c", script),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return result.stdout.splitlines()[-1] == "True"


def test_cli_import_does_not_load_treestamps(tmp_path: Path) -> None:
    assert not _loads_treestamps("import picopt.cli", tmp_path)


def test_doctor_does_not_load_treestamps(tmp_path: Path) -> None:
    code = (
        "from picopt import cli\n"
        "try:\n"
        "    cli.main(('picopt', 'doctor'))\n"
        "except SystemExit:\n"
        "    pass\n"
    )
    assert not _loads_treestamps(code, tmp_path)
