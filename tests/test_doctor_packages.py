"""The doctor checks picopt's direct dependencies against their pins."""

from importlib.metadata import PackageNotFoundError

import pytest

from picopt.doctor import packages
from picopt.doctor.result import FAIL, OK, WARN

__all__ = ()


def _fake_metadata(
    monkeypatch: pytest.MonkeyPatch,
    requirements: tuple[str, ...] | None,
    installed: dict[str, str],
) -> None:
    def _requires(_dist: str) -> tuple[str, ...]:
        if requirements is None:
            raise PackageNotFoundError(_dist)
        return requirements

    def _version(name: str) -> str:
        try:
            return installed[name]
        except KeyError:
            raise PackageNotFoundError(name) from None

    monkeypatch.setattr(packages, "requires", _requires)
    monkeypatch.setattr(packages, "version", _version)


def test_all_satisfied(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_metadata(
        monkeypatch,
        ("confuse~=2.3", "Pillow>=12.0"),
        {
            "confuse": "2.3.1",
            "Pillow": "12.3.0",
        },
    )
    [row] = packages.check_packages()
    assert row.status is OK
    assert row.detail == "2 requirements satisfied"


def test_missing_package_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_metadata(monkeypatch, ("confuse~=2.3", "rarfile~=4.0"), {"confuse": "2.3"})
    [row] = packages.check_packages()
    assert row.status is FAIL
    assert row.name == "rarfile"
    assert row.detail == "missing"


def test_treestamps_outside_pin_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    # The concrete trap: 5.1.0 also fails to import on Python 3.11.
    _fake_metadata(monkeypatch, ("treestamps~=5.2.0",), {"treestamps": "5.1.1"})
    [row] = packages.check_packages()
    assert row.status is FAIL
    assert row.name == "treestamps"
    assert row.detail == "5.1.1 does not satisfy ~=5.2.0"


def test_prerelease_inside_pin_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_metadata(monkeypatch, ("treestamps~=5.2.0",), {"treestamps": "5.2.1a1"})
    [row] = packages.check_packages()
    assert row.status is OK


def test_false_marker_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_metadata(
        monkeypatch,
        (
            "confuse~=2.3",
            'absent-extra-dep>=1; extra == "docs"',
            'absent-old-python-dep>=1; python_version < "3.0"',
        ),
        {"confuse": "2.3"},
    )
    [row] = packages.check_packages()
    assert row.status is OK
    assert row.detail == "1 requirement satisfied"


def test_no_picopt_metadata_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_metadata(monkeypatch, None, {})
    [row] = packages.check_packages()
    assert row.status is WARN


def test_real_install_is_satisfied() -> None:
    rows = packages.check_packages()
    assert [row.status for row in rows] == [OK], rows
