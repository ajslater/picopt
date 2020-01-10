"""Test handling files module."""
from pathlib import Path
from typing import Tuple
from unittest import TestCase

from picopt import files
from picopt.settings import Settings


__all__ = ()  # hides module from pydocstring
SETTINGS = Settings()


class TestCleanupAterOptimise(TestCase):

    TEST_FN_OLD: str = "/tmp/TEST_FILE.{}"
    TEST_FN_NEW: str = "/tmp/TEST_FILE.{}.NEW"

    @staticmethod
    def create_file(fn_template: str, ext: str, num_chars: int) -> Path:
        path = Path(fn_template.format(ext))
        path.write_text("x" * num_chars)
        return path

    @classmethod
    def cleanup_aux(
        cls,
        old_size: int,
        new_size: int,
        old_format: str,
        new_format: str,
        settings: Settings = SETTINGS,
        cause_error: bool = False,
    ) -> Tuple[Path, int, int]:
        if cause_error:
            old_path = Path("/tmp/old")
            new_path = Path("/tmp/new")
        else:
            old_path = cls.create_file(cls.TEST_FN_OLD, old_format, old_size)
            new_path = cls.create_file(cls.TEST_FN_NEW, new_format, new_size)
        res = files._cleanup_after_optimize_aux(
            settings, old_path, new_path, old_format, new_format
        )
        if res[0].exists():
            Path(res[0]).unlink()
        return res

    def test_small_big(self) -> None:
        old_size = 32
        new_size = 40
        old_format = "png"
        new_format = "png"
        path, b_in, b_out = self.cleanup_aux(old_size, new_size, old_format, new_format)
        self.assertEqual(path.suffix, "." + old_format)
        self.assertEqual(old_size, b_in)
        self.assertEqual(old_size, b_out)

    def test_big_small(self) -> None:
        old_size = 44
        new_size = 4
        old_format = "bmp"
        new_format = "png"
        path, b_in, b_out = self.cleanup_aux(old_size, new_size, old_format, new_format)
        print("Assert", path.suffix, "==", "." + new_format)
        self.assertEqual(path.suffix, "." + new_format)
        self.assertEqual(old_size, b_in)
        self.assertEqual(new_size, b_out)

    def test_small_small(self) -> None:
        old_size = 5
        new_size = 5
        old_format = "bmp"
        new_format = "png"
        path, b_in, b_out = self.cleanup_aux(old_size, new_size, old_format, new_format)
        self.assertEqual(path.suffix, "." + old_format)
        self.assertEqual(old_size, b_in)
        self.assertEqual(old_size, b_out)

    def test_small_big_format_change_bigger(self) -> None:
        old_size = 5
        new_size = 50
        old_format = "bmp"
        new_format = "png"
        settings = Settings(set(), SETTINGS)
        settings.bigger = True
        settings.test = True
        path, b_in, b_out = self.cleanup_aux(
            old_size, new_size, old_format, new_format, settings
        )
        self.assertEqual(path.suffix, "." + new_format)
        self.assertEqual(old_size, b_in)
        self.assertEqual(new_size, b_out)

    def test_small_big_bigger(self) -> None:
        old_size = 5
        new_size = 50
        old_format = "png"
        new_format = "png"
        settings = Settings(set(), SETTINGS)
        settings.bigger = True
        settings.test = True
        path, b_in, b_out = self.cleanup_aux(
            old_size, new_size, old_format, new_format, settings
        )
        self.assertEqual(path.suffix, "." + new_format)
        self.assertEqual(old_size, b_in)
        self.assertEqual(new_size, b_out)

    def test_os_error(self) -> None:
        old_size = 5
        new_size = 50
        old_format = "png"
        new_format = "png"
        settings = Settings(set(), SETTINGS)
        settings.bigger = True
        settings.test = True
        path, b_in, b_out = self.cleanup_aux(
            old_size, new_size, old_format, new_format, settings, True
        )
        self.assertEqual(path.suffix, "")
        self.assertEqual(0, b_in)
        self.assertEqual(0, b_out)

    def test_cleanup_after_optimize(self) -> None:
        old_size = 32
        new_size = 5
        old_format = "bmp"
        new_format = "png"
        old_path = self.create_file(self.TEST_FN_OLD, old_format, old_size)
        new_path = self.create_file(self.TEST_FN_OLD, new_format, new_size)
        res = files.cleanup_after_optimize(SETTINGS, old_path, new_path, "bmp", "png")
        assert res.final_path == Path(self.TEST_FN_OLD.format(new_format))
        assert res.bytes_in == old_size
        assert res.bytes_out == new_size
