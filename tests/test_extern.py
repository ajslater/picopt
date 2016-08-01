from unittest import TestCase

from picopt import extern

class TestDoesExernalProgramRun(TestCase):

    def test_true(self):
        res = extern.does_external_program_run('true')
        self.assertTrue(res)

    def test_garbage(self):
        res = extern.does_external_program_run('asdkfjadskl')
        self.assertFalse(res)


class TestRunExt(TestCase):
    def test_true(self):
        extern.run_ext('true')
