import unittest

import mock
from parameterized import parameterized


from conan.internal.api.detect_api import detect_gcc_compiler


class GCCCompilerTestCase(unittest.TestCase):

    @parameterized.expand([("10",), ("4.2",), ('7', )])
    def test_detect_gcc_10(self, version):
        with mock.patch("platform.system", return_value="Linux"):
            with mock.patch("conan.internal.api.detect_api.detect_runner", return_value=(0, version)):
                compiler, installed_version, compiler_exe = detect_gcc_compiler()
        self.assertEqual(compiler, 'gcc')
        self.assertEqual(installed_version, version)
        self.assertEqual(compiler_exe, 'gcc')
