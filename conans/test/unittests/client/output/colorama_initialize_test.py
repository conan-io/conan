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
        with environment_append({PYCHARM_HOSTED: "1"}):

            with environment_append({CONAN_COLOR_DISPLAY: "1"}):

                def colorama_init(convert, strip):
                    self.assertEqual(convert, False)
                    self.assertEqual(strip, False)

                with mock.patch("conans.client.output.colorama_init", side_effect=colorama_init) as m:
                    ret = colorama_initialize()
                    self.assertEqual(ret, True)
                    self.assertTrue(m.called)

            with environment_append({CONAN_COLOR_DISPLAY: "0"}):
                with mock.patch("conans.client.output.colorama_init", side_effect=None) as m:
                    ret = colorama_initialize()
                    self.assertEqual(ret, False)
                    self.assertFalse(m.called)

    def test_not_pycharm_hosted(self, _):
        with environment_append({PYCHARM_HOSTED: ""}):

            with environment_append({CONAN_COLOR_DISPLAY: "1"}):

                def colorama_init(convert='not-set', strip='not-set'):
                    self.assertEqual(convert, 'not-set')
                    self.assertEqual(strip, 'not-set')

                with mock.patch("conans.client.output.colorama_init", side_effect=colorama_init) as m:
                    ret = colorama_initialize()
                    self.assertEqual(ret, True)
                    self.assertTrue(m.called)

            with environment_append({CONAN_COLOR_DISPLAY: "0"}):
                with mock.patch("conans.client.output.colorama_init", side_effect=False) as m:
                    ret = colorama_initialize()
                    self.assertEqual(ret, False)
                    self.assertFalse(m.called)


@mock.patch('sys.stdout.isatty', return_value=False)
class ColoramaInitializeNoTTY(unittest.TestCase):

    def test_pycharm_hosted(self, _):
        with environment_append({PYCHARM_HOSTED: "1"}):

            with environment_append({CONAN_COLOR_DISPLAY: "1"}):

                def colorama_init(convert, strip):
                    self.assertEqual(convert, False)
                    self.assertEqual(strip, False)

                with mock.patch("conans.client.output.colorama_init", side_effect=colorama_init) as m:
                    ret = colorama_initialize()
                    self.assertEqual(ret, True)
                    self.assertTrue(m.called)

            with environment_append({CONAN_COLOR_DISPLAY: "0"}):
                with mock.patch("conans.client.output.colorama_init", side_effect=False) as m:
                    ret = colorama_initialize()
                    self.assertEqual(ret, False)
                    self.assertFalse(m.called)

    def test_not_pycharm_hosted(self, _):
        with environment_append({PYCHARM_HOSTED: ""}):

            with environment_append({CONAN_COLOR_DISPLAY: "1"}):

                def colorama_init(convert='not-set', strip='not-set'):
                    self.assertEqual(convert, 'not-set')
                    self.assertEqual(strip, 'not-set')

                with mock.patch("conans.client.output.colorama_init", side_effect=colorama_init) as m:
                    ret = colorama_initialize()
                    self.assertEqual(ret, True)
                    self.assertTrue(m.called)

            with environment_append({CONAN_COLOR_DISPLAY: "0"}):
                with mock.patch("conans.client.output.colorama_init", side_effect=False) as m:
                    ret = colorama_initialize()
                    self.assertEqual(ret, False)
                    self.assertFalse(m.called)
