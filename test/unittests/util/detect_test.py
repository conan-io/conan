import unittest

import mock
from unittest.mock import patch
import pytest
from parameterized import parameterized

from conan.internal.api.detect_api import _cc_compiler
from conans.client.conf.detect import detect_defaults_settings
from conans.model.version import Version
from conan.test.utils.mocks import RedirectedTestOutput
from conan.test.utils.tools import redirect_output
from conan.test.utils.env import environment_update


class DetectTest(unittest.TestCase):
    @mock.patch("platform.machine", return_value="")
    def test_detect_empty_arch(self, _):
        result = detect_defaults_settings()
        result = dict(result)
        self.assertTrue("arch" not in result)

    @parameterized.expand([
        ['powerpc', '64', '7.1.0.0', 'ppc64'],
        ['powerpc', '32', '7.1.0.0', 'ppc32'],
        ['rs6000', None, '4.2.1.0', 'ppc32']
    ])
    def test_detect_aix(self, processor, bitness, version, expected_arch):
        with mock.patch("platform.machine", mock.MagicMock(return_value='XXXXXXXXXXXX')), \
                mock.patch("platform.processor", mock.MagicMock(return_value=processor)), \
                mock.patch("platform.system", mock.MagicMock(return_value='AIX')), \
                mock.patch("conan.internal.api.detect_api._get_aix_conf", mock.MagicMock(return_value=bitness)), \
                mock.patch('subprocess.check_output', mock.MagicMock(return_value=version)):
            result = detect_defaults_settings()
            result = dict(result)
            self.assertEqual("AIX", result['os'])
            self.assertEqual(expected_arch, result['arch'])

    @parameterized.expand([
        ['arm64', 'armv8'],
        ['i386', 'x86'],
        ['i686', 'x86'],
        ['i86pc', 'x86'],
        ['amd64', 'x86_64'],
        ['aarch64', 'armv8'],
        ['sun4v', 'sparc']
    ])
    def test_detect_arch(self, machine, expected_arch):
        with mock.patch("platform.machine", mock.MagicMock(return_value=machine)):
            result = detect_defaults_settings()
            result = dict(result)
            self.assertEqual(expected_arch, result['arch'])

    @mock.patch("conan.internal.api.detect_api.detect_clang_compiler",
                return_value=("clang", Version("9"), "clang"))
    def test_detect_clang_gcc_toolchain(self, _):
        output = RedirectedTestOutput()
        with redirect_output(output):
            with environment_update({"CC": "clang-9 --gcc-toolchain=/usr/lib/gcc/x86_64-linux-gnu/9"}):
                detect_defaults_settings()
                self.assertIn("CC and CXX: clang-9 --gcc-toolchain", output)


@pytest.mark.parametrize("version_return,expected_version", [
    ["cc.exe (Rev3, Built by MSYS2 project) 14.1.0", "14.1.0"],
    ["g++ (Conan-Build-gcc--binutils-2.42) 14.1.0", "14.1.0"],
    ["clang version 18.1.0rc (https://github.com/llvm/llvm-project.git 461274b81d8641eab64d494accddc81d7db8a09e)", "18.1.0"],
    ["cc.exe (Rev3, Built by MSYS2 project) 14.0", "14.0"],
    ["clang version 18 (https://github.com/llvm/llvm-project.git 461274b81d8641eab64d494accddc81d7db8a09e)", "18"],
    ["cc.exe (Rev3, Built by MSYS2 project) 14", "14"],
])
@patch("conan.internal.api.detect_api.detect_runner")
def test_detect_cc_versionings(detect_runner_mock, version_return, expected_version):
    detect_runner_mock.return_value = 0, version_return
    compiler, installed_version, compiler_exe = _cc_compiler()
    assert installed_version == Version(expected_version)
