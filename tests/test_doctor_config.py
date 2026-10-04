"""The doctor's Config section: read errors, unknown keys and provenance."""

from pathlib import Path

import pytest

from picopt import config as picopt_config
from picopt.config import TotalRam
from picopt.doctor import config as doctor_config
from tests.doctor_util import find_row, isolate_config, run_doctor

__all__ = ()


@pytest.fixture(autouse=True)
def config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = isolate_config(monkeypatch, tmp_path)
    path.mkdir()
    return path


def _write_user_config(config_dir: Path, text: str) -> Path:
    path = config_dir / "config.yaml"
    path.write_text(text)
    return path


def test_bad_yaml_fails_without_traceback(
    config_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_user_config(config_dir, "picopt:\n  recurse: [unclosed\n")
    code, out = run_doctor(capsys)
    assert code == 1
    row = find_row(out, "FAIL", "read")
    assert row is not None
    assert str(path) in row
    # The rest of the report still renders.
    assert "tier 0 ok" in out
    assert find_row(out, "off", "not checked") is not None
    assert "Traceback" not in capsys.readouterr().err


def test_misspelt_key_suggests(
    config_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_user_config(config_dir, "picopt:\n  convert-to: [WEBP]\n")
    _, out = run_doctor(capsys)
    row = find_row(out, "WARN", "unknown key")
    assert row is not None
    assert "picopt.convert-to" in row
    assert row.endswith("did you mean convert_to?")


def test_key_outside_envelope(
    config_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_user_config(config_dir, "recurse: true\n")
    _, out = run_doctor(capsys)
    row = find_row(out, "WARN", "outside picopt:")
    assert row is not None
    assert row.endswith("ignored; nest it under picopt:")


def test_unknown_env_var_is_named(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PICOPT_PICOPT__RECURS", "1")
    _, out = run_doctor(capsys)
    row = find_row(out, "WARN", "unknown key")
    assert row == "WARN unknown key PICOPT_PICOPT__RECURS: did you mean recurse?"


def test_disable_programs_typo(
    config_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_user_config(config_dir, "picopt:\n  disable_programs: [oxipnng]\n")
    _, out = run_doctor(capsys)
    row = find_row(out, "WARN", "disable_programs")
    assert row is not None
    assert row.endswith("'oxipnng' matches no tool: did you mean oxipng?")


def test_provenance_labels(
    config_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    user_path = _write_user_config(config_dir, "picopt:\n  extra_formats: [WEBP]\n")
    cli_config = tmp_path / "my.yaml"
    cli_config.write_text("picopt:\n  formats: [PNG]\n")
    monkeypatch.setenv("PICOPT_PICOPT__BIGGER", "true")
    _, out = run_doctor(capsys, "-C", str(cli_config), "-r")
    # The normalizers .set() formats and extra_formats, which would hide
    # their real sources; the raw layered config still has them.
    assert find_row(out, "", "extra_formats") == (
        f"extra_formats [WEBP] from user config {user_path}"
    )
    assert find_row(out, "", "formats") == f"formats [PNG] from -C {cli_config}"
    assert find_row(out, "", "bigger") == "bigger true from env"
    assert find_row(out, "", "recurse") == "recurse true from command line"
    assert find_row(out, "", "keep_metadata") is None


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("-c", "FOO"), "must be one of"),
        (("-A", "garbage"), "Unparsable --after value"),
        (("--memory-limit", "banana"), "Unparsable --memory-limit value"),
    ],
)
def test_invalid_values_fail(
    args: tuple[str, ...], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run_doctor(capsys, *args)
    assert code == 1
    row = find_row(out, "FAIL", "invalid")
    assert row is not None
    assert message in row


def test_ram_fallback_warns(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fallback = TotalRam(4 * 1024**3, detected=False)
    monkeypatch.setattr(picopt_config, "detect_total_ram", lambda: fallback)
    monkeypatch.setattr(doctor_config, "detect_total_ram", lambda: fallback)
    code, out = run_doctor(capsys)
    assert code == 0
    row = find_row(out, "WARN", "memory budget")
    assert row is not None
    assert "2730 MiB" in row
    assert "RAM not detected" in row


def test_memory_budget_set(capsys: pytest.CaptureFixture[str]) -> None:
    _, out = run_doctor(capsys, "--memory-limit", "8G")
    assert find_row(out, "", "memory budget") == "memory budget 8192 MiB (set to 8G)"
