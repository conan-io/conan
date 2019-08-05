# coding=utf-8

import sys
import unittest

import os
import mock
from parameterized import parameterized

from conans.client.output import colorama_initialize
from conans.client.tools.env import environment_append

CONAN_COLOR_DISPLAY = 'CONAN_COLOR_DISPLAY'
PYCHARM_HOSTED = 'PYCHARM_HOSTED'


class ColoramaInitialize(unittest.TestCase):

    @parameterized.expand([(True, ), (False, )])  # pycharm_hosted
    @mock.patch('sys.stdout.isatty', return_value=True)
    def test_tty_true(self, pycharm_hosted, _):
        assert hasattr(sys.stdout, 'isatty')
        self.assertTrue(sys.stdout.isatty())  # Double check

        PYCHARM_HOSTED_VALUE = "1" if pycharm_hosted else ""
        CONVERT_VALUE = False if pycharm_hosted else 'not-set'
        STRIP_VALUE = False if pycharm_hosted else 'not-set'

        def colorama_init(convert='not-set', strip='not-set'):
            self.assertEqual(convert, CONVERT_VALUE)
            self.assertEqual(strip, STRIP_VALUE)

        with environment_append({PYCHARM_HOSTED: PYCHARM_HOSTED_VALUE}):
            # CONAN_COLOR_DISPLAY not in environment
            assert CONAN_COLOR_DISPLAY not in os.environ
            with mock.patch("conans.client.output.colorama_init", side_effect=colorama_init) as m:
                ret = colorama_initialize()
                self.assertEqual(ret, True)
                self.assertTrue(m.called)

            # CONAN_COLOR_DISPLAY equals ~True
            with environment_append({CONAN_COLOR_DISPLAY: "1"}):
                with mock.patch("conans.client.output.colorama_init", side_effect=colorama_init) as m:
                    ret = colorama_initialize()
                    self.assertEqual(ret, True)
                    self.assertTrue(m.called)

            # CONAN_COLOR_DISPLAY equals ~False
            with environment_append({CONAN_COLOR_DISPLAY: "0"}):
                with mock.patch("conans.client.output.colorama_init", side_effect=False) as m:
                    ret = colorama_initialize()
                    self.assertEqual(ret, False)
                    self.assertFalse(m.called)

    @parameterized.expand([(True, ), (False, )])  # pycharm_hosted
    @mock.patch('sys.stdout.isatty', return_value=False)
    def test_tty_false(self, pycharm_hosted, _):
        self.assertFalse(hasattr(sys.stdout, 'isatty') and sys.stdout.isatty())

        PYCHARM_HOSTED_VALUE = "1" if pycharm_hosted else ""
        CONVERT_VALUE = False if pycharm_hosted else 'not-set'
        STRIP_VALUE = False if pycharm_hosted else 'not-set'

        def colorama_init(convert='not-set', strip='not-set'):
            self.assertEqual(convert, CONVERT_VALUE)
            self.assertEqual(strip, STRIP_VALUE)

        with environment_append({PYCHARM_HOSTED: PYCHARM_HOSTED_VALUE}):
            # CONAN_COLOR_DISPLAY not in environment
            assert CONAN_COLOR_DISPLAY not in os.environ
            with mock.patch("conans.client.output.colorama_init", side_effect=colorama_init) as m:
                ret = colorama_initialize()
                self.assertEqual(ret, False)
                self.assertFalse(m.called)

            # CONAN_COLOR_DISPLAY equals ~True
            with environment_append({CONAN_COLOR_DISPLAY: "1"}):
                with mock.patch("conans.client.output.colorama_init", side_effect=colorama_init) as m:
                    ret = colorama_initialize()
                    self.assertEqual(ret, True)
                    self.assertTrue(m.called)

            # CONAN_COLOR_DISPLAY equals ~False
            with environment_append({CONAN_COLOR_DISPLAY: "0"}):
                with mock.patch("conans.client.output.colorama_init", side_effect=False) as m:
                    ret = colorama_initialize()
                    self.assertEqual(ret, False)
                    self.assertFalse(m.called)
