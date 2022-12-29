import os
import textwrap

import pytest
from mock import patch

from conan.tools._compilers import architecture_flag, cppstd_flag
from conan.tools.intel import IntelCC
from conans.errors import ConanException
from conans.model.conf import ConfDefinition
from conans.test.utils.mocks import ConanFileMock, MockSettings


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
    flag = architecture_flag(settings)
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
    settings = MockSettings({
        "compiler": "intel-cc",
        "compiler.version": "2021.3",
        "compiler.mode": "classic",
        "arch": "x86_64",
        "os": "Linux",
        "compiler.cppstd": cppstd
    })
    assert cppstd_flag(settings) == "-std=%s" % flag


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


def test_installation_path_in_conf():
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({
        "compiler.version": "2021.3",
        "compiler.mode": "classic",
        "os": "Windows"
    })
    fake_path = "mysuper/path/to/intel/oneapi"
    conanfile.conf = ConfDefinition()
    conanfile.conf.loads(textwrap.dedent("""\
        tools.intel:installation_path=%s
    """ % fake_path))
    assert IntelCC(conanfile).installation_path == fake_path


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
