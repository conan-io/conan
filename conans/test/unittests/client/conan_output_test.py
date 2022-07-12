# coding=utf-8
import sys
import unittest
from unittest import mock

from parameterized import parameterized

from conan.output import ConanOutput
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
