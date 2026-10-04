"""A broken format library disables only its own plugin."""

import importlib
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from picopt import plugins as registry
from tests import IMAGES_DIR

__all__ = ()

_JPEG = IMAGES_DIR / "test_jpg.jpg"
# Each library, and the plugin module its failure must disable.
_LIBRARIES = (("rarfile", "rar"), ("py7zr", "seven_zip"), ("pikepdf", "pdf"))


def _run_blocked(
    library: str, code: str, tmp_path: Path
) -> subprocess.CompletedProcess[str]:
    """Run code in a fresh interpreter where ``library`` fails to import."""
    # Imports are cached per process, so blocking a library needs a new one.
    script = f"import sys\nsys.modules[{library!r}] = None\n{code}"
    # Wide enough that no report row wraps.
    env = {**os.environ, "PICOPTDIR": str(tmp_path / "config"), "COLUMNS": "200"}
    return subprocess.run(  # noqa: S603
        (sys.executable, "-c", script),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


@pytest.mark.parametrize(("library", "module"), _LIBRARIES)
class TestBrokenLibrary:
    """Each library's failure disables its own plugin and nothing else."""

    def test_import_survives(self, library: str, module: str, tmp_path: Path) -> None:
        code = (
            "from picopt import cli, plugins\n"
            "print([f.module for f in plugins.failed_plugins()])\n"
            "print(sorted(p.name for p in plugins.iter_plugins()))\n"
        )
        result = _run_blocked(library, code, tmp_path)
        assert result.returncode == 0, result.stderr
        failed, loaded = result.stdout.splitlines()
        assert failed == repr([module])
        assert "JPEG" in loaded
        assert "PNG" in loaded

    def test_jpeg_still_optimizes(
        self, library: str, module: str, tmp_path: Path
    ) -> None:
        path = tmp_path / "test.jpg"
        shutil.copy(_JPEG, path)
        code = f"from picopt import cli\ncli.main(('picopt', {str(path)!r}))\n"
        result = _run_blocked(library, code, tmp_path)
        assert result.returncode == 0, result.stderr
        assert path.stat().st_size < _JPEG.stat().st_size
        warning = f"Plugin '{module}' disabled"
        assert result.stdout.count(warning) == 1, result.stdout
        assert library in result.stdout

    def test_doctor_reports_failed_plugin(
        self, library: str, module: str, tmp_path: Path
    ) -> None:
        code = "from picopt import cli\ncli.main(('picopt', 'doctor'))\n"
        result = _run_blocked(library, code, tmp_path)
        assert result.returncode == 1, result.stderr
        assert "Traceback" not in result.stderr
        [row] = [
            line for line in result.stdout.splitlines() if "failed to load" in line
        ]
        assert row.split()[:2] == ["FAIL", module]
        assert library in row


def test_placeholder_never_matches(tmp_path: Path) -> None:
    """Archive members of other kinds still convert with rarfile missing."""
    code = (
        "from zipfile import ZipInfo\n"
        "from picopt.archiveinfo import ArchiveInfo\n"
        "info = ArchiveInfo(ZipInfo('dir/a.txt', (2020, 1, 2, 3, 4, 6)))\n"
        "print(info.filename(), info.is_dir(), info.to_tarinfo().name)\n"
    )
    result = _run_blocked("rarfile", code, tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["dir/a.txt", "False", "dir/a.txt"]


@pytest.fixture
def rediscover() -> Iterator[None]:
    """Run discovery afresh, then restore the real result."""
    registry._discover.cache_clear()
    yield
    registry._discover.cache_clear()


def _fail_import(
    monkeypatch: pytest.MonkeyPatch, target: str, error: ImportError
) -> None:
    real_import_module = importlib.import_module

    def _import_module(name: str, package: str | None = None):
        if name == target:
            raise error
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", _import_module)


@pytest.mark.usefixtures("rediscover")
class TestDiscoveryIsolation:
    """Only third-party ImportErrors are isolated."""

    def test_third_party_import_error_is_isolated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        error = ModuleNotFoundError("No module named 'somelib'", name="somelib")
        with monkeypatch.context() as patch:
            _fail_import(patch, "picopt.plugins.svg", error)
            discovery = registry._discover()
        [failure] = discovery.failures
        assert failure.module == "svg"
        assert failure.error is error
        assert "SVG" not in {plugin.name for plugin in discovery.plugins}

    def test_picopt_import_error_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        error = ImportError("cannot import name 'X'", name="picopt.plugins.base")
        with monkeypatch.context() as patch:
            _fail_import(patch, "picopt.plugins.svg", error)
            with pytest.raises(ImportError, match="cannot import name 'X'"):
                registry._discover()
