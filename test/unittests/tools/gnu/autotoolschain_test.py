from unittest.mock import patch

import pytest

from conan.tools.build import cmd_args_to_string
from conan.tools.gnu import AutotoolsToolchain
from conans.errors import ConanException
from conans.model.conf import Conf
from conan.test.utils.mocks import ConanFileMock, MockSettings


@pytest.fixture()
def cross_building_conanfile():
    settings_build = MockSettings({"os": "Linux",
                                   "arch": "x86_64",
                                   "compiler": "gcc",
                                   "compiler.version": "11",
                                   "compiler.libcxx": "libstdc++",
                                   "build_type": "Release"})
    settings_target = MockSettings({"os": "Android", "arch": "armv8"})
    settings = MockSettings({"os": "Emscripten", "arch": "wasm"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.settings_build = settings_build
    conanfile.settings_target = settings_target
    return conanfile


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
    settings = MockSettings({"build_type": "Release" if "d" not in runtime else "Debug",
                             "compiler": "msvc",
                             "compiler.runtime": "static" if "MT" in runtime else "dynamic",
                             "compiler.runtime_type": "Release" if "d" not in runtime else "Debug",
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
                             "arch": "x86_64",
                             "compiler": "gcc"})
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
                             "compiler": "gcc",
                             "arch": "x86_64"})
    conanfile.settings = settings
    autotoolschain = AutotoolsToolchain(conanfile)
    env = autotoolschain.environment().vars(conanfile)
    assert "-T'path_to_first_linker_script'" in env["LDFLAGS"]
    assert "-T'path_to_second_linker_script'" in env["LDFLAGS"]


@patch("conan.tools.gnu.autotoolstoolchain.save_toolchain_args")
def test_check_configure_args_overwriting_and_deletion(save_args, cross_building_conanfile):
    # Issue: https://github.com/conan-io/conan/issues/12642
    at = AutotoolsToolchain(cross_building_conanfile)
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
    # https://github.com/conan-io/conan/issues/12431
    at.configure_args.remove("--build=x86_64-linux-gnu")
    at.configure_args.remove("--host=wasm32-local-emscripten")
    at.generate_args()
    configure_args = save_args.call_args[0][0]['configure_args']
    assert "--build=x86_64-linux-gnu" not in configure_args  # removed
    assert "--host=wasm32-local-emscripten" not in configure_args  # removed
    assert "--with-cross-build=my_path" in configure_args
    assert "--something-host=my_host" in configure_args


def test_update_or_prune_any_args(cross_building_conanfile):
    at = AutotoolsToolchain(cross_building_conanfile)
    at.configure_args.append("--enable-flag1=false")
    # Update configure_args
    at.update_configure_args({"--prefix": "/my/other/prefix",
                              "--build": None,  # prune value
                              "--enable-flag1": "",  # without value
                              "-NEW-FLAG": "no"  # new flag
                              })
    new_configure_args = cmd_args_to_string(at.configure_args)
    assert "--prefix=/my/other/prefix" in new_configure_args
    assert "--build=" not in new_configure_args  # pruned
    assert "--enable-flag1" in new_configure_args  # flag without value
    assert "-NEW-FLAG=no" in new_configure_args  # new flag
    # Update autoreconf_args
    at.update_autoreconf_args({"--force": None})
    new_autoreconf_args = cmd_args_to_string(at.autoreconf_args)
    assert "'--force" not in new_autoreconf_args
    # Add new value to make_args
    at.update_make_args({"--new-complex-flag": "new-value"})
    new_make_args = cmd_args_to_string(at.make_args)
    assert "--new-complex-flag=new-value" in new_make_args


def test_tricore():
    settings = MockSettings({"build_type": "Release",
                             "compiler": "gcc",
                             "os": "baremetal",
                             "arch": "tc131"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.settings_build = settings
    autotoolschain = AutotoolsToolchain(conanfile)
    env = autotoolschain.environment().vars(conanfile)
    assert '-mtc131' in env["CFLAGS"]
    assert '-mtc131' in env["CXXFLAGS"]
    assert '-mtc131' in env["LDFLAGS"]
