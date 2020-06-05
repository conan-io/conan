# coding=utf-8

import unittest
from types import MethodType

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

    def test_output_color(self):
        # Output is not a terminal, no overrides.
        # Color generation disabled.
        with mock.patch("colorama.init") as init:
            isatty = False
            env = {}
            with mock.patch("sys.stdout.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                assert not colorama_initialize()
                init.assert_not_called()

        # Output is a terminal, no overrides.
        # Color generation enabled, colorama will not strip colors.
        with mock.patch("colorama.init") as init:
            isatty = True
            env = {}
            with mock.patch("sys.stdout.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                assert colorama_initialize()
                init.assert_called_once_with()

        # Output is not a terminal, prevent color generation (CONAN_COLOR_DISPLAY=0).
        # Color generation disabled.
        with mock.patch("colorama.init") as init:
            isatty = False
            env = {"CONAN_COLOR_DISPLAY": "0"}
            with mock.patch("sys.stdout.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                assert not colorama_initialize()
                init.assert_not_called()

        # Output is a terminal, prevent color generation (CONAN_COLOR_DISPLAY=0).
        # Color generation disabled.
        with mock.patch("colorama.init") as init:
            isatty = True
            env = {"CONAN_COLOR_DISPLAY": "0"}
            with mock.patch("sys.stdout.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                assert not colorama_initialize()
                init.assert_not_called()

        # Output is not a terminal, force color generation (CONAN_COLOR_DISPLAY=1).
        # Color generation enabled, colorama will strip colors.
        with mock.patch("colorama.init") as init:
            isatty = False
            env = {"CONAN_COLOR_DISPLAY": "1"}
            with mock.patch("sys.stdout.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                assert colorama_initialize()
                init.assert_called_once_with()

        # Output is a terminal, force color generation (CONAN_COLOR_DISPLAY=1).
        # Color generation enabled, colorama will not strip colors.
        with mock.patch("colorama.init") as init:
            isatty = True
            env = {"CONAN_COLOR_DISPLAY": "1"}
            with mock.patch("sys.stdout.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                assert colorama_initialize()
                init.assert_called_once_with()

        # Output is not a terminal, no forced color generation, prevent color stripping
        # (PYCHARM_HOSTED=1).
        # Color generation disabled.
        with mock.patch("colorama.init") as init:
            isatty = False
            env = {"PYCHARM_HOSTED": "1"}
            with mock.patch("sys.stdout.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                assert not colorama_initialize()
                init.assert_not_called()

        # Output is not a terminal, force color generation (CONAN_COLOR_DISPLAY=1),
        # prevent color stripping (PYCHARM_HOSTED=1).
        # Color generation enabled, colorama will not strip colors (forced).
        with mock.patch("colorama.init") as init:
            isatty = False
            env = {"PYCHARM_HOSTED": "1", "CONAN_COLOR_DISPLAY": "1"}
            with mock.patch("sys.stdout.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                assert colorama_initialize()
                init.assert_called_once_with(convert=False, strip=False)

        # Output is a terminal, prevent color generation (CONAN_COLOR_DISPLAY=0), prevent
        # color stripping (PYCHARM_HOSTED=1).
        # Color generation disabled.
        with mock.patch("colorama.init") as init:
            isatty = True
            env = {"PYCHARM_HOSTED": "1", "CONAN_COLOR_DISPLAY": "0"}
            with mock.patch("sys.stdout.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                assert not colorama_initialize()
                init.assert_not_called()

        # Output is a terminal, prevent color stripping (PYCHARM_HOSTED=1).
        # Color generation enabled, colorama will not strip colors.
        with mock.patch("colorama.init") as init:
            isatty = True
            env = {"PYCHARM_HOSTED": "1"}
            with mock.patch("sys.stdout.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                assert colorama_initialize()
                init.assert_called_once_with(convert=False, strip=False)
