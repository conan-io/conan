import unittest

import mock
from parameterized import parameterized

from conans.client.conf.detect import _gcc_compiler
from conans.test.utils.mocks import TestBufferConanOutput


class GCCCompilerTestCase(unittest.TestCase):

    @parameterized.expand([("10",), ("4.2",), ('7', )])
    def test_detect_gcc_10(self, version):
        output = TestBufferConanOutput()
        with mock.patch("platform.system", return_value="Linux"):
            with mock.patch("conans.client.conf.detect.detect_runner", return_value=(0, version)):
                compiler, installed_version = _gcc_compiler(output)
        self.assertEqual(compiler, 'gcc')
        self.assertEqual(installed_version, version)
