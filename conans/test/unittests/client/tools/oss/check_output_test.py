# coding=utf-8

import os
import unittest

import six

from conans.client.tools.oss import check_output, ConanSubprocessError


class CheckOutputTestCase(unittest.TestCase):

    success_code = 0

    def test_command_success(self):
        ret = check_output('ls {}'.format(os.path.dirname(__file__)))
        self.assertTrue(isinstance(ret, six.string_types))
        self.assertIn("check_output_test.py\n", ret)

    def test_working_dir(self):
        cwd = os.path.join(os.path.dirname(__file__), '..')
        ret = check_output("ls", folder=cwd)
        self.assertTrue(isinstance(ret, six.string_types))
        self.assertIn("oss\n", ret)

    def test_return_code(self):
        ret = check_output("ls", return_code=True)
        self.assertTrue(isinstance(ret, int))
        self.assertEqual(self.success_code, ret)

    def test_error_call(self):
        with self.assertRaises(ConanSubprocessError) as e:
            ret = check_output("asdf")
            self.assertEqual(None, ret)
        self.assertIn("Command 'asdf' returned non-zero exit status", str(e.exception))
        self.assertNotEqual(self.success_code, e.exception.returncode)

    def test_error_return_code(self):
        ret = check_output("asdf", return_code=True)
        self.assertNotEqual(self.success_code, ret)
