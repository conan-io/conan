from unittest.mock import patch

import pytest

from conan.tools.gnu import AutotoolsToolchain
from conans.errors import ConanException
from conans.model.conf import Conf
from conans.test.utils.mocks import ConanFileMock, MockSettings


def test_get_gnu_triplet_for_cross_building():
    """
    Testing AutotoolsToolchain and _get_gnu_triplet() function in case of
    having os=Windows and cross compiling
    """
    # Issue: https://github.com/conan-io/conan/issues/10139
    settings = MockSettings({"build_type": "Release",
                             "compiler": "gcc",
                             "compiler.version": "10.2",
                             "os": "Windows",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.settings_build = MockSettings({"os": "Solaris", "arch": "x86"})
    autotoolschain = AutotoolsToolchain(conanfile)
    assert autotoolschain._host == "x86_64-w64-mingw32"
    assert autotoolschain._build == "i686-solaris"


def test_get_toolchain_cppstd():
    settings = MockSettings({"build_type": "Release",
                             "compiler": "gcc",
                             "compiler.version": "10",
                             "compiler.cppstd": "20",
                             "os": "Linux",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.settings_build = settings
    autotoolschain = AutotoolsToolchain(conanfile)
    assert autotoolschain.cppstd == "-std=c++2a"
    settings.values["compiler.version"] = "12"
    autotoolschain = AutotoolsToolchain(conanfile)
    assert autotoolschain.cppstd == "-std=c++20"


@pytest.mark.parametrize("runtime, runtime_type, expected",
                         [("static", "Debug", "MTd"),
                          ("static", "Release", "MT"),
                          ("dynamic", "Debug", "MDd"),
                          ("dynamic", "Release", "MD")])
def test_msvc_runtime(runtime, runtime_type, expected):
    """
    Testing AutotoolsToolchain with the msvc compiler adjust the runtime
    """
    # Issue: https://github.com/conan-io/conan/issues/10139
    settings = MockSettings({"build_type": "Release",
                             "compiler": "msvc",
                             "compiler.runtime": runtime,
                             "compiler.runtime_type": runtime_type,
                             "os": "Windows",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.settings_build = settings
    autotoolschain = AutotoolsToolchain(conanfile)
    expected_flag = "-{}".format(expected)
    assert autotoolschain.msvc_runtime_flag == expected_flag
    env = autotoolschain.environment().vars(conanfile)
    assert expected_flag in env["CFLAGS"]
    assert expected_flag in env["CXXFLAGS"]


@pytest.mark.parametrize("runtime", ["MTd", "MT", "MDd", "MD"])
def test_visual_runtime(runtime):
    """
    Testing AutotoolsToolchain with the msvc compiler adjust the runtime
    """
    # Issue: https://github.com/conan-io/conan/issues/10139
    settings = MockSettings({"build_type": "Release",
                             "compiler": "Visual Studio",
                             "compiler.runtime": runtime,
                             "os": "Windows",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.settings_build = settings
    autotoolschain = AutotoolsToolchain(conanfile)
    expected_flag = "-{}".format(runtime)
    assert autotoolschain.msvc_runtime_flag == expected_flag
    env = autotoolschain.environment().vars(conanfile)
    assert expected_flag in env["CFLAGS"]
    assert expected_flag in env["CXXFLAGS"]


def test_get_gnu_triplet_for_cross_building_raise_error():
    """
    Testing AutotoolsToolchain and _get_gnu_triplet() function raises an error in case of
    having os=Windows, cross compiling and not defined any compiler
    """
    # Issue: https://github.com/conan-io/conan/issues/10139
    settings = MockSettings({"build_type": "Release",
                             "os": "Windows",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.settings_build = MockSettings({"os": "Solaris", "arch": "x86"})
    with pytest.raises(ConanException) as conan_error:
        AutotoolsToolchain(conanfile)
        msg = "'compiler' parameter for 'get_gnu_triplet()' is not specified and " \
              "needed for os=Windows"
        assert msg == str(conan_error.value)


def test_compilers_mapping():
    autotools_mapping = {"c": "CC", "cpp": "CXX", "cuda": "NVCC", "fortran": "FC"}
    compilers = {"c": "path_to_c", "cpp": "path_to_cpp", "cuda": "path_to_cuda",
                 "fortran": "path_to_fortran"}
    settings = MockSettings({"build_type": "Release",
                             "os": "Windows",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.conf.define("tools.build:compiler_executables", compilers)
    conanfile.settings = settings
    autotoolschain = AutotoolsToolchain(conanfile)
    env = autotoolschain.environment().vars(conanfile)
    for compiler, env_var in autotools_mapping.items():
        assert env[env_var] == f"path_to_{compiler}"


def test_linker_scripts():
    conanfile = ConanFileMock()
    conanfile.conf = Conf()
    conanfile.conf.define("tools.build:linker_scripts", ["path_to_first_linker_script", "path_to_second_linker_script"])
    settings = MockSettings({"build_type": "Release",
                             "os": "Windows",
                             "arch": "x86_64"})
    conanfile.settings = settings
    autotoolschain = AutotoolsToolchain(conanfile)
    env = autotoolschain.environment().vars(conanfile)
    assert "-T'path_to_first_linker_script'" in env["LDFLAGS"]
    assert "-T'path_to_second_linker_script'" in env["LDFLAGS"]


@patch("conan.tools.gnu.autotoolstoolchain.save_toolchain_args")
def test_check_configure_args_overwriting(save_args):
    # Issue: https://github.com/conan-io/conan/issues/12642
    settings_build = MockSettings({"os": "Linux",
                                   "arch": "x86_64",
                                   "compiler": "gcc",
                                   "compiler.version": "11",
                                   "compiler.libcxx": "libstdc++",
                                   "build_type": "Release"})
    settings = MockSettings({"os": "Emscripten",
                             "arch": "wasm"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.settings_build = settings_build
    at = AutotoolsToolchain(conanfile)
    at.configure_args.extend([
        "--with-cross-build=my_path",
        "--something-host=my_host"
    ])
    at.generate_args()
    configure_args = save_args.call_args[0][0]['configure_args']
    assert "--build=x86_64-linux-gnu" in configure_args
    assert "--host=wasm32-local-emscripten" in configure_args
    assert "--with-cross-build=my_path" in configure_args
    assert "--something-host=my_host" in configure_args
