import os
from unittest import TestCase

from picopt import files

class TestReplaceExt(TestCase):

    @staticmethod
    def make_ext(base, ext):
        return '{}.{}'.format(base, ext)

    def replace_aux(self, file_base, old_ext, new_ext):
        old_filename = self.make_ext(file_base, old_ext)
        new_filename = self.make_ext(file_base, new_ext)
        res = files.replace_ext(old_filename, new_ext)
        self.assertEquals(new_filename, res)

    def test_regular(self):
        self.replace_aux('test_file', 'foo', 'bar')

    def test_with_dots(self):
        self.replace_aux('test.file', 'foo', 'bar')


class TestCleanupAterOptimise(TestCase):

    TEST_FN_OLD = '/tmp/TEST_FILE_OLD.{}'
    TEST_FN_NEW = '/tmp/TEST_FILE_NEW.{}'

    @staticmethod
    def create_file(fn_template, ext, num_chars):
        filename = fn_template.format(ext)
        with open(filename, 'w') as test_file:
            test_file.write('x' * num_chars)
        return filename

    @classmethod
    def cleanup_aux(self, old_size, new_size, old_format, new_format):
        fn_old = self.create_file(self.TEST_FN_OLD, old_format, old_size)
        fn_new = self.create_file(self.TEST_FN_NEW, new_format, new_size)
        res = files._cleanup_after_optimize_aux(fn_old, fn_new,
                                                old_format, new_format)
        os.remove(res[0])
        return res


    def test_small_big(self):
        old_size = 32
        new_size = 40
        old_format = 'png'
        new_format = 'png'
        fn, b_in, b_out = self.cleanup_aux(old_size, new_size, old_format,
                                           new_format)
        self.assertTrue(fn.endswith(old_format))
        self.assertEqual(old_size, b_in)
        self.assertEqual(old_size, b_out)

    def test_big_small(self):
        old_size = 44
        new_size = 4
        old_format = 'bmp'
        new_format = 'png'
        fn, b_in, b_out = self.cleanup_aux(old_size, new_size, old_format,
                                           new_format)
        self.assertTrue(fn.endswith(new_format))
        self.assertEqual(old_size, b_in)
        self.assertEqual(new_size, b_out)

    def test_small_small(self):
        old_size = 5
        new_size = 5
        old_format = 'bmp'
        new_format = 'png'
        fn, b_in, b_out = self.cleanup_aux(old_size, new_size, old_format,
                                           new_format)
        self.assertTrue(fn.endswith(old_format))
        self.assertEqual(old_size, b_in)
        self.assertEqual(old_size, b_out)
