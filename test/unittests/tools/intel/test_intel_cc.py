import os
import textwrap

import pytest
from unittest.mock import patch

from conan.tools.build.flags import architecture_flag, sycl_flag, cppstd_flag
from conan.tools.build.compiler import compiler_executables
from conan.tools.intel import IntelCC
from conan.errors import ConanException
from conan.internal.model.conf import ConfDefinition
from conan.test.utils.mocks import ConanFileMock, MockSettings


@pytest.mark.parametrize("os_,arch,expected", [
    ("Windows", "x86", "/Qm32"),
    ("Windows", "x86_64", "/Qm64"),
    ("Linux", "x86", "-m32"),
    ("Linux", "x86_64", "-m64")
])
def test_architecture_flag_if_intel_cc(os_, arch, expected):
    settings = MockSettings({
        "compiler": "intel-cc",
        "compiler.version": "2021.3",
        "compiler.mode": "classic",
        "arch": arch,
        "os": os_
    })
    conanfile = ConanFileMock()
    conanfile.settings = settings
    flag = architecture_flag(conanfile)
    assert flag == expected


@pytest.mark.parametrize("cppstd,flag", [
    ("98", "c++98"),
    ("gnu98", "gnu++98"),
    ("03", "c++03"),
    ("gnu03", "gnu++03"),
    ("11", "c++11"),
    ("gnu11", "gnu++11"),
    ("14", "c++14"),
    ("gnu14", "gnu++14"),
    ("17", "c++17"),
    ("gnu17", "gnu++17"),
    ("20", "c++20"),
    ("gnu20", "gnu++20"),
    ("23", "c++2b"),
    ("gnu23", "gnu++2b"),
])
def test_cppstd_flag_if_intel_cc(cppstd, flag):
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({
        "compiler": "intel-cc",
        "compiler.version": "2021.3",
        "compiler.mode": "classic",
        "arch": "x86_64",
        "os": "Linux",
        "compiler.cppstd": cppstd
    })
    assert cppstd_flag(conanfile) == "-std=%s" % flag


@pytest.mark.parametrize("mode", ["icx", "dpcpp"])
def test_macos_not_supported_for_new_compilers(mode):
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({
        "compiler.version": "2021.3",
        "compiler.mode": mode,
        "os": "Darwin"
    })
    with pytest.raises(ConanException) as excinfo:
        IntelCC(conanfile)
    assert "macOS* is not supported for the icx/icpx or dpcpp compilers." in str(excinfo.value)


@pytest.mark.parametrize("os_", ["Windows", "Linux", "Darwin"])
def test_error_if_detected_intel_legacy_version(os_):
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({
        "compiler.version": "19.1",
        "compiler.mode": "classic",
        "os": os_
    })
    with pytest.raises(ConanException) as excinfo:
        IntelCC(conanfile)
    assert "You have to use 'intel' compiler which is meant for legacy" in str(excinfo.value)


@pytest.mark.parametrize("os_", ["Windows", "Linux", "Darwin"])
def test_classic_compiler_supports_every_os(os_):
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({
        "compiler.version": "2021.3",
        "compiler.mode": "classic",
        "os": os_,
        "arch": "x86_64"
    })
    assert IntelCC(conanfile).arch == "x86_64"


@pytest.mark.parametrize("mode,expected", [
    ("icx", "Intel C++ Compiler 2021"),
    ("dpcpp", "Intel(R) oneAPI DPC++ Compiler"),
    ("classic", "Intel C++ Compiler 19.2")
])
def test_check_ms_toolsets(mode, expected):
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({
        "compiler.version": "2021.3",
        "compiler.mode": mode,
        "os": "Windows"
    })
    assert IntelCC(conanfile).ms_toolset == expected


@pytest.mark.parametrize("mode,version,expected_cc,expected_cxx", [
    ("icx", "2021.3", "icx", "icpx"),
    ("icx", "2026.0", "icx", "icpx"),
    ("dpcpp", "2021.3", "icx", "dpcpp"),  # dpcpp available before 2024.0
    ("dpcpp", "2026.0", "icx", "icpx"),   # dpcpp deprecated >= 2024.0, use icpx
    ("classic", "2021.3", "icc", "icpc"),
])
def test_compiler_executables(mode, version, expected_cc, expected_cxx):
    """Test that compiler_executables returns the correct executables based on mode and version"""
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({
        "compiler": "intel-cc",
        "compiler.version": version,
        "compiler.mode": mode,
    })
    result = compiler_executables(conanfile)
    assert result["c"] == expected_cc
    assert result["cpp"] == expected_cxx


@pytest.mark.parametrize("mode,version,expected", [
    ("dpcpp", "2021.3", ""),       # dpcpp < 2024, no extra flags needed
    ("dpcpp", "2026.0", "-fsycl"),  # dpcpp >= 2024, needs -fsycl
    ("icx", "2026.0", ""),         # icx mode, no sycl flags
])
def test_sycl_flag(mode, version, expected):
    """Test that sycl_flag returns -fsycl for dpcpp >= 2024"""
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({
        "compiler": "intel-cc",
        "compiler.version": version,
        "compiler.mode": mode,
    })
    assert sycl_flag(conanfile) == expected


def test_installation_path_in_conf():
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({
        "compiler.version": "2021.3",
        "compiler.mode": "classic",
        "os": "Windows"
    })
    fake_path = "mysuper/path/to/intel/oneapi"
    conanfile.conf = ConfDefinition()
    conanfile.conf.loads(textwrap.dedent(f'tools.intel:installation_path={fake_path}'))
    assert IntelCC(conanfile).installation_path == fake_path


def test_invalid_installation_path_in_conf():
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({
        "compiler.version": "2026.0",
        "os": "Windows"
    })

    conanfile.conf = ConfDefinition()
    conanfile.conf.loads(textwrap.dedent('tools.intel:installation_path=""'))
    with pytest.raises(ConanException) as e:
        IntelCC(conanfile).generate()
    assert "Invalid 'tools.intel:installation_path'" in str(e.value)


@pytest.mark.parametrize("os_,call_command,setvars_file", [
    ("Windows", "call", "setvars.bat"),
    ("Linux", ".", "setvars.sh")
])
@patch("conan.tools.intel.intel_cc.platform.system")
def test_setvars_command_with_custom_arguments(platform_system, os_, call_command, setvars_file):
    platform_system.return_value = os_
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({
        "compiler.version": "2021.3",
        "compiler.mode": "icx",
        "os": os_
    })
    fake_path = "mysuper/path/to/intel/oneapi"
    args = "arg1 arg2 --force"
    conanfile.conf = ConfDefinition()
    conanfile.conf.loads(textwrap.dedent("""\
        tools.intel:installation_path=%s
        tools.intel:setvars_args=%s
    """ % (fake_path, args)))
    expected = '%s "%s" %s' % (call_command, os.path.join(fake_path, setvars_file), args)
    assert IntelCC(conanfile).command == expected
