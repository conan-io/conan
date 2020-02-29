# coding=utf-8

import unittest
from types import MethodType

from six import StringIO

from conans.client.output import ConanOutput
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
