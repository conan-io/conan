import mock
from unittest.mock import patch
import pytest

from conan.internal.api.detect.detect_api import _cc_compiler, detect_suncc_compiler, \
    detect_intel_compiler
from conan.internal.api.profile.detect import detect_defaults_settings
from conan.internal.model.version import Version
from conan.test.utils.mocks import RedirectedTestOutput
from conan.test.utils.tools import redirect_output
from conan.test.utils.env import environment_update


class TestDetect:
    @mock.patch("platform.machine", return_value="")
    def test_detect_empty_arch(self, _):
        result = detect_defaults_settings()
        result = dict(result)
        assert "arch" not in result

    @pytest.mark.parametrize("processor,bitness,version,expected_arch", [
        ['powerpc', '64', '7.1.0.0', 'ppc64'],
        ['powerpc', '32', '7.1.0.0', 'ppc32'],
        ['rs6000', None, '4.2.1.0', 'ppc32']
    ])
    def test_detect_aix(self, processor, bitness, version, expected_arch):
        with mock.patch("platform.machine", mock.MagicMock(return_value='XXXXXXXXXXXX')), \
                mock.patch("platform.processor", mock.MagicMock(return_value=processor)), \
                mock.patch("platform.system", mock.MagicMock(return_value='AIX')), \
                mock.patch("conan.internal.api.detect.detect_api._get_aix_conf", mock.MagicMock(return_value=bitness)), \
                mock.patch('subprocess.check_output', mock.MagicMock(return_value=version)):
            result = detect_defaults_settings()
            result = dict(result)
            assert "AIX" == result['os']
            assert expected_arch == result['arch']

    @pytest.mark.parametrize("machine,expected_arch", [
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
            assert expected_arch == result['arch']

    @mock.patch("conan.internal.api.detect.detect_api.detect_clang_compiler",
                return_value=("clang", Version("9"), "clang"))
    def test_detect_clang_gcc_toolchain(self, _):
        output = RedirectedTestOutput()
        with redirect_output(output):
            with environment_update({"CC": "clang-9 --gcc-toolchain=/usr/lib/gcc/x86_64-linux-gnu/9"}):
                detect_defaults_settings()
                assert "CC and CXX: clang-9 --gcc-toolchain" in output


@pytest.mark.parametrize("version_return,expected_version", [
    ["cc.exe (Rev3, Built by MSYS2 project) 14.1.0", "14.1.0"],
    ["g++ (Conan-Build-gcc--binutils-2.42) 14.1.0", "14.1.0"],
    ["gcc.exe (x86_64-posix-seh-rev0, Built by MinGW-Builds project) 15.1.0", "15.1.0"],
    ["gcc.exe (x86_64-posix-seh-rev0, Built by MinGW-Builds project) 15.15.0", "15.15.0"],
    ["gcc (crosstool-NG 1.27.0) 13.3.0", "13.3.0"],
    ["gcc (crosstool-NG 1.27.0) 13.3", "13.3"],
    ["gcc (GCC) 4.8.1", "4.8.1"],
    ["clang version 18.1.0rc (https://github.com/llvm/llvm-project.git 461274b81d8641eab64d494accddc81d7db8a09e)", "18.1.0"],
    ["cc.exe (Rev3, Built by MSYS2 project) 14.0", "14.0"],
    ["clang version 18 (https://github.com/llvm/llvm-project.git 461274b81d8641eab64d494accddc81d7db8a09e)", "18"],
    ["cc.exe (Rev3, Built by MSYS2 project) 14", "14"],
    ["cc.exe 14.2", "14.2"],
    ["cc1 14.2", "14.2"],
])
@patch("conan.internal.api.detect.detect_api.detect_runner")
def test_detect_cc_versioning(detect_runner_mock, version_return, expected_version):
    detect_runner_mock.return_value = 0, version_return
    compiler, installed_version, compiler_exe = _cc_compiler()
    # Using private _value attribute to compare the str that reaches it, so no space issues arise
    assert installed_version._value == Version(expected_version)._value
    assert installed_version == Version(expected_version)

@pytest.mark.parametrize("function,version_return,expected_version", [
    [detect_suncc_compiler, "Sun C 5.13", ('sun-cc', Version("5.13"), 'cc')],
    [detect_intel_compiler, "Intel C++ Compiler 2025.0", ('intel-cc', Version("2025.0"), 'icx')],
])
def test_detect_compiler(function, version_return, expected_version):
    with mock.patch("conan.internal.api.detect.detect_api.detect_runner", mock.MagicMock(return_value=(0, version_return))):
        ret = function()
        assert ret == expected_version
