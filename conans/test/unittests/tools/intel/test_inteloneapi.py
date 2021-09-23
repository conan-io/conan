import os
import textwrap

import pytest
from mock import patch, Mock

from conan.tools.intel import IntelOneAPI
from conans.client.tools import environment_append
from conans.errors import ConanException
from conans.model.conf import ConfDefinition
from conans.test.utils.mocks import ConanFileMock, MockSettings


@pytest.mark.parametrize("mode", ["icx", "dpcpp"])
def test_macos_not_supported_for_new_compilers(mode):
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({
        "compiler.version": "2021.3",
        "compiler.mode": mode,
        "os": "Darwin"
    })
    with pytest.raises(ConanException) as excinfo:
        IntelOneAPI(conanfile)
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
        IntelOneAPI(conanfile)
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
    assert IntelOneAPI(conanfile).arch == "x86_64"


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
    assert IntelOneAPI(conanfile).ms_toolset == expected


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
    assert IntelOneAPI(conanfile).installation_path == fake_path


@pytest.mark.parametrize("os_,call_command,setvars_file", [
    ("Windows", "call", "setvars.bat"),
    ("Linux", ".", "setvars.sh")
])
@patch("conan.tools.intel.inteloneapi.platform.system")
def test_setvars_command_with_custom_arguments(platform_system, os_, call_command, setvars_file):
    platform_system.return_value = os_
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({
        "compiler.version": "2021.3",
        "compiler.mode": "icx",
        "os": os_
    })
    fake_path = "mysuper/path/to/intel/oneapi"
    args = "arg1 arg2"
    conanfile.conf = ConfDefinition()
    conanfile.conf.loads(textwrap.dedent("""\
        tools.intel:installation_path=%s
        tools.intel:setvars_args=%s
    """ % (fake_path, args)))
    expected = '%s "%s" %s' % (call_command, os.path.join(fake_path, setvars_file), args)
    assert IntelOneAPI(conanfile).command == expected


def test_setvars_command_is_already_loaded():
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({
        "compiler.version": "2021.3",
        "compiler.mode": "icx",
        "os": "Linux"
    })
    fake_path = "mysuper/path/to/intel/oneapi"
    args = "arg1 arg2"
    conanfile.conf = ConfDefinition()
    conanfile.conf.loads(textwrap.dedent("""\
        tools.intel:installation_path=%s
        tools.intel:setvars_args=%s
    """ % (fake_path, args)))
    with environment_append({"SETVARS_COMPLETED": "1"}):
        assert IntelOneAPI(conanfile).command == "echo Conan:intel_setvars already set! " \
                                                 "Pass --force if you want to reload it"


@patch("conan.tools.intel.inteloneapi.platform.system", new=Mock(return_value="Linux"))
def test_setvars_command_is_already_loaded_but_force_is_passed():
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({
        "compiler.version": "2021.3",
        "compiler.mode": "icx",
        "os": "Linux"
    })
    fake_path = "mysuper/path/to/intel/oneapi"
    args = "arg1 arg2 --force"
    conanfile.conf = ConfDefinition()
    conanfile.conf.loads(textwrap.dedent("""\
        tools.intel:installation_path=%s
        tools.intel:setvars_args=%s
    """ % (fake_path, args)))
    expected = '. "%s" %s' % (os.path.join(fake_path, "setvars.sh"), args)
    with environment_append({"SETVARS_COMPLETED": "1"}):
        assert IntelOneAPI(conanfile).command == expected
