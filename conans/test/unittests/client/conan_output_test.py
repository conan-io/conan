# coding=utf-8
import sys
import unittest
from types import MethodType
from unittest import mock

import pytest
from parameterized import parameterized
from six import StringIO

from conans.cli.output import ConanOutput
from conans.client.userio import init_colorama


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
        with mock.patch("sys.stderr", stream):
            init_colorama(sys.stderr)
            out = ConanOutput()
            with mock.patch("time.sleep") as sleep:
                out.write("Hello world")
                sleep.assert_any_call(0.02)
        self.assertEqual("Hello world", stream.getvalue())

    @parameterized.expand([(False, {}),
                           (True, {"CLICOLOR": "0"}),
                           (False, {"CLICOLOR": "1"}),
                           (False, {"CLICOLOR_FORCE": "0"})])
    def test_output_no_color(self, isatty, env):
        with mock.patch("colorama.init") as init:
            with mock.patch("sys.stderr.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                init_colorama(sys.stderr)
                out = ConanOutput()
                assert out.color is False
                init.assert_called()

    @parameterized.expand([(True, {}),
                           (False, {"CLICOLOR_FORCE": "1"}),
                           (True, {"CLICOLOR": "1"})])
    def test_output_color(self, isatty, env):
        with mock.patch("colorama.init") as init:
            with mock.patch("sys.stderr.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                init_colorama(sys.stderr)
                out = ConanOutput()
                assert out.color is True
                init.assert_called()

    @parameterized.expand([(True, {"NO_COLOR": "1"}),
                           (True, {"NO_COLOR": "1", "CLICOLOR_FORCE": "1"}),
                           (True, {"NO_COLOR": "1", "CLICOLOR_FORCE": "1", "CLICOLOR": "1"}),
                           (False, {"NO_COLOR": "1", "CLICOLOR_FORCE": "1", "CLICOLOR": "1"})])
    def test_output_color_prevent_strip(self, isatty, env):
        with mock.patch("colorama.init") as init:
            with mock.patch("sys.stderr.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                init_colorama(sys.stderr)
                out = ConanOutput()
                assert out.color is False
                init.assert_not_called()
