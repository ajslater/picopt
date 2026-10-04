"""Probes that must fail when a run would fail, so routing skips cleanly."""

import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import rarfile
from PIL import Image

from picopt import PROGRAM_NAME, cli
from picopt import plugins as registry
from picopt.config import PicoptConfig
from picopt.config.settings import PicoptSettings
from picopt.plugins import jxl as jxl_plugin
from picopt.plugins import rar as rar_plugin
from picopt.plugins.base.tool import PILSaveTool, Tool
from picopt.plugins.jxl import JxlLossless
from picopt.plugins.rar import Cbr, Rar
from picopt.plugins.tar import Tar, TarGz, TarXz
from picopt.plugins.webp.animated import PILPackWebPAnimatedLossless
from picopt.plugins.webp.static import WebPLossless
from picopt.walk.walk import Walk
from tests import CONTAINER_DIR, IMAGES_DIR

__all__ = ()

_RAR5_SIGNATURE = b"Rar!\x1a\x07\x01\x00"
_PROBE_FIXTURE = Path(rar_plugin.__file__).with_name("_rar_probe.rar")


def _all_tools() -> Iterator[Tool]:
    """Every distinct tool instance; handlers share pipelines."""
    yield from dict.fromkeys(
        tool
        for handler_cls in registry.all_handlers()
        for tier in handler_cls.PIPELINE
        for tool in tier
    )


def _pil_save_tools(format_str: str) -> tuple[PILSaveTool, ...]:
    return tuple(
        tool
        for tool in _all_tools()
        if isinstance(tool, PILSaveTool) and tool.target_format_str == format_str
    )


@pytest.fixture
def fresh_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forget every cached probe; monkeypatch restores them afterwards."""
    for tool in _all_tools():
        monkeypatch.setattr(tool, "_probed_status", None)


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PICOPTDIR", str(tmp_path / "config"))


def _settings(*args: str, path: Path) -> PicoptSettings:
    arguments = cli.get_arguments((PROGRAM_NAME, "-q", *args, str(path)))
    return PicoptConfig().get_config(arguments)


def _drop_pil_save(monkeypatch: pytest.MonkeyPatch, format_str: str) -> None:
    """Make Pillow look built without a codec."""
    # Fill the lazy registries first so the probe's init() can't refill them.
    Image.init()
    monkeypatch.delitem(Image.SAVE, format_str)
    monkeypatch.delitem(Image.SAVE_ALL, format_str)


def _walk_unchanged(settings: PicoptSettings, path: Path) -> None:
    """Run picopt and assert it skipped the file without an error."""
    before = path.read_bytes()
    stats = Walk(settings).walk()
    assert not stats.errors
    assert stats.skipped == 1
    assert path.read_bytes() == before


@pytest.mark.usefixtures("fresh_probes")
class TestPillowSaveProbe:
    """A Pillow without a codec's save handler must not route to it."""

    def test_jxl_without_codec(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _drop_pil_save(monkeypatch, "JXL")
        [pil2jxl] = _pil_save_tools("JXL")
        status = pil2jxl.probe()
        assert not status.available
        assert "Pillow has no JXL save support" in status.error

        path = tmp_path / "test.jxl"
        shutil.copy(IMAGES_DIR / "test_jxl_lossless.jxl", path)
        settings = _settings("-f", "JXL", path=path)
        assert JxlLossless not in settings.computed.handler_stages
        _walk_unchanged(settings, path)

    def test_jxl_error_names_import_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _drop_pil_save(monkeypatch, "JXL")
        error = ModuleNotFoundError("No module named 'pillow_jxl'")
        monkeypatch.setattr(jxl_plugin, "PILLOW_JXL_IMPORT_ERROR", error)
        [pil2jxl] = _pil_save_tools("JXL")
        assert str(error) in pil2jxl.probe().error

    def test_webp_without_libwebp(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _drop_pil_save(monkeypatch, "WEBP")
        pil2webps = _pil_save_tools("WEBP")
        assert pil2webps
        assert not any(tool.probe().available for tool in pil2webps)

        path = tmp_path / "test.webp"
        shutil.copy(IMAGES_DIR / "test_webp_lossless.webp", path)
        # Without cwebp too, nothing can write still WebP.
        settings = _settings("-f", "WEBP", "-D", "cwebp", path=path)
        handler_stages = settings.computed.handler_stages
        assert WebPLossless not in handler_stages
        assert PILPackWebPAnimatedLossless not in handler_stages
        _walk_unchanged(settings, path)

    def test_formats_with_save_support_stay_available(self) -> None:
        for format_str in ("PNG", "GIF", "WEBP", "JXL"):
            for tool in _pil_save_tools(format_str):
                assert tool.probe().available, format_str


@pytest.mark.usefixtures("fresh_probes")
class TestTarCodecProbe:
    """Each compressed tar handler needs its codec module."""

    def test_missing_lzma_drops_only_txz(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setitem(sys.modules, "lzma", None)
        status = TarXz.PIPELINE[0][0].probe()
        assert not status.available
        assert "lzma" in status.error
        assert Tar.PIPELINE[0][0].probe().available
        assert TarGz.PIPELINE[0][0].probe().available

        settings = _settings("-x", "TAR,TGZ,TXZ", path=tmp_path)
        handler_stages = settings.computed.handler_stages
        assert TarXz not in handler_stages
        assert Tar in handler_stages
        assert TarGz in handler_stages

    def test_codec_in_version(self) -> None:
        assert TarXz.PIPELINE[0][0].probe().version.endswith(" +lzma")
        assert "+" not in Tar.PIPELINE[0][0].probe().version


class TestRarProbeFixture:
    """The shipped fixture must exercise an external tool."""

    def test_fixture_is_rar5(self) -> None:
        assert _PROBE_FIXTURE.read_bytes().startswith(_RAR5_SIGNATURE)

    def test_fixture_member_is_compressed(self) -> None:
        # rarfile reads stored members itself, so a stored probe would pass
        # with no tool installed at all.
        with rarfile.RarFile(_PROBE_FIXTURE) as archive:
            [info] = archive.infolist()
        assert info.compress_type != rarfile.RAR_M0


@pytest.mark.usefixtures("fresh_probes")
class TestUnrarProbe:
    """unrar passes only if rarfile can extract a compressed member."""

    def test_real_unrar_extracts(self) -> None:
        status = Rar.PIPELINE[0][0].probe()
        assert status.available, status.error
        assert status.detail == "extracts RAR5"

    def test_extraction_failure_is_unavailable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def _fail(*_args, **_kwargs):
            reason = "Unsupported Method"
            raise rarfile.BadRarFile(reason)

        monkeypatch.setattr(rarfile.RarFile, "read", _fail)
        status = Rar.PIPELINE[0][0].probe()
        assert not status.available
        assert "cannot extract RAR5" in status.error
        assert "Unsupported Method" in status.error
        # The binary was found, so its path survives for the report.
        assert status.path

        path = tmp_path / "test.cbr"
        shutil.copy(CONTAINER_DIR / "test_cbr.cbr", path)
        settings = _settings("-x", "CBR,RAR", "-c", "CBZ,ZIP", path=path)
        handler_stages = settings.computed.handler_stages
        assert Rar not in handler_stages
        assert Cbr not in handler_stages
        _walk_unchanged(settings, path)
        assert not path.with_suffix(".cbz").exists()

    def test_swapped_backend_is_named(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(rar_plugin, "rar_extract_error", lambda: "")
        bsdtar_setup = rarfile.ToolSetup(rarfile.BSDTAR_CONFIG)
        monkeypatch.setattr(rarfile, "CURRENT_SETUP", bsdtar_setup)
        status = Rar.PIPELINE[0][0].probe()
        assert status.available
        assert status.detail == "extracts RAR5 via bsdtar"

    def test_unreadable_backend_drops_only_the_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(rar_plugin, "rar_extract_error", lambda: "")
        monkeypatch.setattr(rarfile, "CURRENT_SETUP", None)
        status = Rar.PIPELINE[0][0].probe()
        assert status.available
        assert status.detail == "extracts RAR5"
