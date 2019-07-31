# coding=utf-8

import unittest
import mock
import sys
from conans.client.output import colorama_initialize
from conans.client.tools.env import environment_append


CONAN_COLOR_DISPLAY = 'CONAN_COLOR_DISPLAY'
PYCHARM_HOSTED = 'PYCHARM_HOSTED'


@mock.patch('sys.stdout.isatty', return_value=True)
class ColoramaInitializeTTY(unittest.TestCase):
    assert hasattr(sys.stdout, 'isatty')

    def test_pycharm_hosted(self, _):
        convert = strip = None

        def colorama_init_mocked(**kwargs):
            global convert, strip
            convert = kwargs.get('convert', 'not-set')
            strip = kwargs.get('strip', 'not-set')

        with mock.patch("colorama.init", side_effect=colorama_init_mocked):
            with environment_append({PYCHARM_HOSTED: "1"}):
                with environment_append({CONAN_COLOR_DISPLAY: "1"}):
                    ret = colorama_initialize()
                    self.assertEqual(ret, True)
                    self.assertEqual(convert, None)
                    self.assertEqual(strip, None)

                with environment_append({CONAN_COLOR_DISPLAY: "0"}):
                    ret = colorama_initialize()
                    self.assertEqual(ret, False)
                    self.assertEqual(convert, None)
                    self.assertEqual(strip, None)

    def test_not_pycharm_hosted(self, _):
        convert = strip = None

        def colorama_init_mocked(**kwargs):
            global convert, strip
            convert = kwargs.get('convert', 'not-set')
            strip = kwargs.get('strip', 'not-set')

        with mock.patch("colorama.init", side_effect=colorama_init_mocked):
            with environment_append({PYCHARM_HOSTED: "1"}):
                with environment_append({CONAN_COLOR_DISPLAY: "1"}):
                    ret = colorama_initialize()
                    self.assertEqual(ret, True)
                    self.assertEqual(convert, None)
                    self.assertEqual(strip, None)

                with environment_append({CONAN_COLOR_DISPLAY: "0"}):
                    ret = colorama_initialize()
                    self.assertEqual(ret, False)
                    self.assertEqual(convert, None)
                    self.assertEqual(strip, None)


@mock.patch('sys.stdout.isatty', return_value=False)
class ColoramaInitializeNoTTY(unittest.TestCase):

    def test_pycharm_hosted(self, _):
        convert = strip = None

        def colorama_init_mocked(**kwargs):
            global convert, strip
            convert = kwargs.get('convert', 'not-set')
            strip = kwargs.get('strip', 'not-set')

        with mock.patch("colorama.init", side_effect=colorama_init_mocked):
            with environment_append({PYCHARM_HOSTED: "1"}):
                with environment_append({CONAN_COLOR_DISPLAY: "1"}):
                    ret = colorama_initialize()
                    self.assertEqual(ret, True)
                    self.assertEqual(convert, None)
                    self.assertEqual(strip, None)

                with environment_append({CONAN_COLOR_DISPLAY: "0"}):
                    ret = colorama_initialize()
                    self.assertEqual(ret, False)
                    self.assertEqual(convert, None)
                    self.assertEqual(strip, None)

    def test_not_pycharm_hosted(self, _):
        convert = strip = None

        def colorama_init_mocked(**kwargs):
            global convert, strip
            convert = kwargs.get('convert', 'not-set')
            strip = kwargs.get('strip', 'not-set')

        with mock.patch("colorama.init", side_effect=colorama_init_mocked):
            with environment_append({PYCHARM_HOSTED: "0"}):
                with environment_append({CONAN_COLOR_DISPLAY: "1"}):
                    ret = colorama_initialize()
                    self.assertEqual(ret, True)
                    self.assertEqual(convert, None)
                    self.assertEqual(strip, None)

                with environment_append({CONAN_COLOR_DISPLAY: "0"}):
                    ret = colorama_initialize()
                    self.assertEqual(ret, False)
                    self.assertEqual(convert, None)
                    self.assertEqual(strip, None)
