# coding=utf-8

import unittest
from types import MethodType

from parameterized import parameterized
from six import StringIO

from conans.client.output import ConanOutput, colorama_initialize
from mock import mock


class ConanOutputTest(unittest.TestCase):

    def test_blocked_output(self):
        # https://github.com/conan-io/conan/issues/4277
        stream = StringIO()

        def write_raise(self, data):
            write_raise.counter = getattr(write_raise, "counter", 0) + 1
            if write_raise.counter < 2:
                raise IOError("Stdout locked")
            self.super_write(data)
        stream.super_write = stream.write
        stream.write = MethodType(write_raise, stream)
        out = ConanOutput(stream)

        with mock.patch("time.sleep") as sleep:
            out.write("Hello world")
            sleep.assert_any_call(0.02)
        self.assertEqual("Hello world", stream.getvalue())

    @parameterized.expand([(False, {}),
                           (False, {"CONAN_COLOR_DISPLAY": "0"}),
                           (True, {"CONAN_COLOR_DISPLAY": "0"}),
                           (False, {"PYCHARM_HOSTED": "1"}),
                           (True, {"PYCHARM_HOSTED": "1", "CONAN_COLOR_DISPLAY": "0"}),
                           (True, {"NO_COLOR": ""}),
                           (True, {"CLICOLOR": "0"}),
                           (True, {"CLICOLOR": "0", "CONAN_COLOR_DISPLAY": "1"}),
                           (False, {"CLICOLOR": "1"}),
                           (False, {"CLICOLOR_FORCE": "0"}),
                           (True,
                            {"CLICOLOR": "1", "CLICOLOR_FORCE": "1", "CONAN_COLOR_DISPLAY": "1",
                             "PYCHARM_HOSTED": "1", "NO_COLOR": "1"})])
    def test_output_no_color(self, isatty, env):
        with mock.patch("colorama.init") as init:
            with mock.patch("sys.stdout.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                assert not colorama_initialize()
                init.assert_not_called()

    @parameterized.expand([(True, {}),
                           (False, {"CONAN_COLOR_DISPLAY": "1"}),
                           (True, {"CONAN_COLOR_DISPLAY": "1"}),
                           (True, {"CLICOLOR": "1"}),
                           (True, {"CLICOLOR_FORCE": "0"})])
    def test_output_color(self, isatty, env):
        with mock.patch("colorama.init") as init:
            with mock.patch("sys.stdout.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                assert colorama_initialize()
                init.assert_called_once_with()

    @parameterized.expand([(False, {"PYCHARM_HOSTED": "1", "CONAN_COLOR_DISPLAY": "1"}),
                           (True, {"PYCHARM_HOSTED": "1"}),
                           (False, {"CLICOLOR_FORCE": "1"}),
                           (True, {"CLICOLOR_FORCE": "1", "CLICOLOR": "0"}),
                           (True, {"CLICOLOR_FORCE": "1", "CONAN_COLOR_DISPLAY": "0"})])
    def test_output_color_prevent_strip(self, isatty, env):
        with mock.patch("colorama.init") as init:
            with mock.patch("sys.stdout.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                assert colorama_initialize()
                init.assert_called_once_with(convert=False, strip=False)
