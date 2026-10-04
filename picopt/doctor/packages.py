"""
Check that picopt's direct dependencies are installed within their pins.

Docker, distro and ``--no-deps`` installs can drift outside the pins, and
some versions are traps: treestamps before 5.1.1 crashes at import on Python
3.11. Reads package metadata only and never imports the packages, so it
runs before plugin discovery and survives a broken import.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, requires, version
from typing import Final

from packaging.requirements import InvalidRequirement, Requirement

from picopt import PROGRAM_NAME
from picopt.doctor.result import FAIL, OK, WARN, CheckResult, plural

SECTION: Final = "Python packages"


def _check_requirement(requirement: Requirement) -> CheckResult | None:
    """Return a FAIL row for an unsatisfied requirement, else None."""
    try:
        installed = version(requirement.name)
    except PackageNotFoundError:
        return CheckResult(SECTION, requirement.name, FAIL, "missing")
    if requirement.specifier.contains(installed, prereleases=True):
        return None
    detail = f"{installed} does not satisfy {requirement.specifier}"
    return CheckResult(SECTION, requirement.name, FAIL, detail)


def _requirements() -> tuple[Requirement, ...] | None:
    """Direct requirements whose markers apply here; None without metadata."""
    try:
        specs = requires(PROGRAM_NAME) or ()
    except PackageNotFoundError:
        return None
    applicable: list[Requirement] = []
    for spec in specs:
        try:
            requirement = Requirement(spec)
        except InvalidRequirement:
            continue
        # Extras' requirements carry an ``extra == ...`` marker, which is
        # false with no extra selected.
        if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
            applicable.append(requirement)
    return tuple(applicable)


def check_packages() -> tuple[CheckResult, ...]:
    """One OK row when every pin holds, else a FAIL row per failure."""
    requirements = _requirements()
    if requirements is None:
        detail = f"{PROGRAM_NAME} package metadata not found"
        return (CheckResult(SECTION, "requirements", WARN, detail),)
    failures = tuple(
        result
        for requirement in requirements
        if (result := _check_requirement(requirement)) is not None
    )
    if failures:
        return failures
    detail = f"{plural(len(requirements), 'requirement')} satisfied"
    return (CheckResult(SECTION, "requirements", OK, detail),)
