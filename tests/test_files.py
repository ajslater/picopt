"""Test handling files."""
from pathlib import Path
from typing import Tuple
from unittest import TestCase

from picopt import files


class TestCleanupAterOptimise(TestCase):

    TEST_FN_OLD: str = '/tmp/TEST_FILE_OLD.{}'
    TEST_FN_NEW: str = '/tmp/TEST_FILE_NEW.{}'

    @staticmethod
    def create_file(fn_template: str, ext: str, num_chars: int) -> Path:
        path = Path(fn_template.format(ext))
        path.write_text('x'*num_chars)
        return path

    @classmethod
    def cleanup_aux(cls, old_size: int, new_size: int,
                    old_format: str,
                    new_format: str) -> Tuple[Path, int, int]:
        old_path = cls.create_file(cls.TEST_FN_OLD, old_format, old_size)
        new_path = cls.create_file(cls.TEST_FN_NEW, new_format, new_size)
        res = files._cleanup_after_optimize_aux(old_path, new_path,
                                                old_format, new_format)
        Path(res[0]).unlink()
        return res

    def test_small_big(self) -> None:
        old_size = 32
        new_size = 40
        old_format = 'png'
        new_format = 'png'
        path, b_in, b_out = self.cleanup_aux(old_size, new_size,
                                             old_format, new_format)
        self.assertEqual(path.suffix, '.'+old_format)
        self.assertEqual(old_size, b_in)
        self.assertEqual(old_size, b_out)

    def test_big_small(self) -> None:
        old_size = 44
        new_size = 4
        old_format = 'bmp'
        new_format = 'png'
        path, b_in, b_out = self.cleanup_aux(old_size, new_size,
                                             old_format, new_format)
        print('Assert', path.suffix, '==', '.'+new_format)
        self.assertEqual(path.suffix, '.'+new_format)
        self.assertEqual(old_size, b_in)
        self.assertEqual(new_size, b_out)

    def test_small_small(self) -> None:
        old_size = 5
        new_size = 5
        old_format = 'bmp'
        new_format = 'png'
        path, b_in, b_out = self.cleanup_aux(old_size, new_size,
                                             old_format, new_format)
        self.assertEqual(path.suffix, '.'+old_format)
        self.assertEqual(old_size, b_in)
        self.assertEqual(old_size, b_out)
