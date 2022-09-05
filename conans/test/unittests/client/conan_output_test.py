# coding=utf-8
import sys
import unittest
from unittest import mock

import pytest
from parameterized import parameterized

from conan.api.output import ConanOutput
from conans.client.userio import init_colorama


class ConanOutputTest(unittest.TestCase):

    @parameterized.expand([(True, {"NO_COLOR": "1"}),
                           (True, {"NO_COLOR": "0"})])
    def test_output_color_prevent_strip(self, isatty, env):
        with mock.patch("colorama.init") as init:
            with mock.patch("sys.stderr.isatty", return_value=isatty), \
                 mock.patch.dict("os.environ", env, clear=True):
                init_colorama(sys.stderr)
                out = ConanOutput()
                assert out.color is False
                init.assert_not_called()


@pytest.mark.parametrize("force", ["1", "0", "foo"])
def test_output_forced(force):
    env = {"CLICOLOR_FORCE": force}
    forced = force != "0"
    with mock.patch("colorama.init") as init:
        with mock.patch("sys.stderr.isatty", return_value=False), \
             mock.patch.dict("os.environ", env, clear=True):
            init_colorama(sys.stderr)
            out = ConanOutput()

            assert out.color is forced
            if not forced:
                init.assert_not_called()


def test_output_forced_but_conan_logger():
    """ If conan is logging, no colors can be forced"""
    env = {"CLICOLOR_FORCE": "1"}
    with mock.patch("conan.api.output.conan_output_logger_format", return_value=True):
        with mock.patch("colorama.init") as init:
            with mock.patch("sys.stderr.isatty", return_value=False), \
                 mock.patch.dict("os.environ", env, clear=True):
                init_colorama(sys.stderr)
                out = ConanOutput()

                assert out.color is False
                init.assert_not_called()
