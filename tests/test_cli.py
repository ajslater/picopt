"""Test cli module."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import argparse

import shutil
import sys
from pathlib import Path

from picopt import cli
from picopt.config import PicoptConfig
from picopt.config.consts import TIMESTAMPS_CONFIG_KEYS
from picopt.plugins.zip import Cbz, Zip
from tests import IMAGES_DIR, get_test_dir

__all__ = ()  # hides module from pydocstring
TMP_ROOT = get_test_dir()
JPEG_SRC = IMAGES_DIR / "test_jpg.jpg"


class TestCLI:
    """Test CLI."""

    OLD_PATH: Path = TMP_ROOT / "old.jpg"

    def setup_method(self: Any) -> None:
        """Set up method."""
        TMP_ROOT.mkdir(exist_ok=True)

    def teardown_method(self: Any) -> None:
        """Tear down method."""
        if TMP_ROOT.exists():
            shutil.rmtree(TMP_ROOT)

    def _test_get_arguments_prepare(self: Any) -> "argparse.Namespace":
        args = ("picopt", "-rqc", "PNG,WEBP", "-x", "CBZ,ZIP", "-bdLM", str(TMP_ROOT))
        arguments = cli.get_arguments(args)
        return arguments.picopt

    def _test_get_arguments_aux(self: Any, arguments: "argparse.Namespace") -> None:
        assert arguments.bigger
        assert not arguments.timestamps
        assert arguments.dry_run
        assert arguments.list_only
        assert not arguments.keep_metadata
        assert arguments.paths[0] == str(TMP_ROOT)

    def test_get_arguments(self: Any) -> None:
        """Test get arguments."""
        arguments = self._test_get_arguments_prepare()
        assert arguments.verbose == 0
        assert arguments.convert_to == ("PNG", "WEBP")
        assert arguments.formats is None
        assert arguments.extra_formats == (
            Cbz.OUTPUT_FORMAT_STR,
            Zip.OUTPUT_FORMAT_STR,
        )
        # Un-passed flags stay None so config-file/env layers aren't
        # shadowed; the config layer's defaults resolve symlinks to True.
        assert arguments.symlinks is None
        self._test_get_arguments_aux(arguments)

    def test_main(self: Any) -> None:
        """Test main method."""
        shutil.copy(JPEG_SRC, self.OLD_PATH)
        old_size = self.OLD_PATH.stat().st_size
        sys.argv = ["picopt", str(self.OLD_PATH)]
        cli.main()
        assert self.OLD_PATH.is_file()
        assert self.OLD_PATH.stat().st_size < old_size

    def test_main_err(self: Any) -> None:
        """Test main errs."""
        sys.argv = ["picopt", "XXX"]
        try:
            cli.main()
        except SystemExit as exc:
            assert exc.code == 1  # noqa: PT017

    def test_memory_limit_parsing(self: Any) -> None:
        """--memory-limit accepts suffixed sizes and resolves to bytes."""
        for arg, expected in (("8G", 8 * 1024**3), ("512M", 512 * 1024**2)):
            args = cli.get_arguments(("picopt", "--memory-limit", arg, str(TMP_ROOT)))
            config = PicoptConfig().get_config(args)
            assert config.memory_limit == expected

    def test_memory_limit_auto(self: Any) -> None:
        """The default (0/auto) resolves to a positive byte budget."""
        args = cli.get_arguments(("picopt", str(TMP_ROOT)))
        config = PicoptConfig().get_config(args)
        assert config.memory_limit > 0

    def test_memory_limit_not_in_timestamp_config(self: Any) -> None:
        """memory_limit must not invalidate existing timestamps."""
        assert "memory_limit" not in TIMESTAMPS_CONFIG_KEYS
