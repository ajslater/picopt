"""``picopt doctor`` dispatch, exit codes and resilience."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from picopt import PROGRAM_NAME, cli
from picopt import plugins as registry
from picopt.doctor.environment import environment_lines

__all__ = ()


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point confuse at an empty config dir and scrub picopt env vars."""
    for key in list(os.environ):
        if key.startswith("PICOPT"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PICOPTDIR", str(tmp_path / "config"))


def _doctor(capsys: pytest.CaptureFixture[str], *args: str) -> tuple[int, str]:
    """Run ``picopt doctor ARGS``; return its exit code and output."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main((PROGRAM_NAME, "doctor", *args))
    code = exc_info.value.code
    assert isinstance(code, int)
    return code, capsys.readouterr().out


def test_healthy_doctor_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _doctor(capsys)
    assert code == 0, out
    for heading in ("Python packages", "Plugins", "Summary: no problems"):
        assert heading in out


def test_discovery_crash_is_a_fail_row(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _crash():
        reason = "boom"
        raise ValueError(reason)

    monkeypatch.setattr(registry, "iter_plugins", _crash)
    code, out = _doctor(capsys)
    assert code == 1
    assert "plugin discovery failed: ValueError: boom" in out
    assert "Python packages" in out
    assert "Summary: 1 problem" in out


def test_environment_names_env_vars_without_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PICOPT_PICOPT__IGNORE", "secret-pattern")
    lines = "\n".join(environment_lines())
    assert "PICOPT_PICOPT__IGNORE" in lines
    assert "secret-pattern" not in lines
    assert lines.startswith(f"{PROGRAM_NAME} ")
    assert "Pillow " in lines


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
