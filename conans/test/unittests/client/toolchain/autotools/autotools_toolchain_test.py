import platform
from os import chdir

import pytest

from conan.tools.files import load_toolchain_args
from conan.tools.gnu import AutotoolsToolchain
from conans.errors import ConanException
from conans.model.conf import Conf
from conans.test.utils.mocks import ConanFileMock, MockSettings, MockOptions
from conans.test.utils.test_files import temp_folder


def test_modify_environment():
    """We can alter the environment generated by the toolchain passing the env to the generate"""
    f = temp_folder()
    chdir(f)
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"os": "Linux", "arch": "x86_64"})
    conanfile.settings_build = MockSettings({"os": "Solaris", "arch": "x86"})
    conanfile.folders.set_base_install(f)
    be = AutotoolsToolchain(conanfile)
    env = be.environment()
    env.define("foo", "var")
    # We can pass the env to the generate once we adjusted or injected anything
    be.generate(env)

    with open("conanautotoolstoolchain.sh") as f:
        content = f.read()
        assert "foo" in content


def test_target_triple():
    f = temp_folder()
    chdir(f)
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"os": "Linux", "arch": "x86_64"})
    conanfile.settings_build = MockSettings({"os": "Solaris", "arch": "x86"})
    conanfile.conf = Conf()
    conanfile.conf["tools.gnu:make_program"] = "my_make"
    conanfile.conf["tools.gnu.make:jobs"] = "23"

    be = AutotoolsToolchain(conanfile)
    be.make_args = ["foo", "var"]
    be.generate_args()
    obj = load_toolchain_args()
    assert "--host=x86_64-linux-gnu" in obj["configure_args"]
    assert "--build=i686-solaris" in obj["configure_args"]
    assert obj["make_args"].replace("'", "") == "foo var"


def test_invalid_target_triple():
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"os": "Linux", "arch": "UNKNOWN_ARCH"})
    conanfile.settings_build = MockSettings({"os": "Solaris", "arch": "x86"})
    with pytest.raises(ConanException) as excinfo:
        AutotoolsToolchain(conanfile)
    assert "Unknown 'UNKNOWN_ARCH' machine, Conan doesn't know how " \
           "to translate it to the GNU triplet," in str(excinfo)


def test_cppstd():
    # Using "cppstd" is discarded
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings(
        {"build_type": "Release",
         "arch": "x86",
         "compiler": "gcc",
         "compiler.libcxx": "libstdc++11",
         "compiler.version": "7.1",
         "cppstd": "17"})
    be = AutotoolsToolchain(conanfile)
    env = be.vars()
    assert "-std=c++17" not in env["CXXFLAGS"]

    # Using "compiler.cppstd" works
    conanfile.settings = MockSettings(
        {"build_type": "Release",
         "arch": "x86",
         "compiler": "gcc",
         "compiler.libcxx": "libstdc++11",
         "compiler.version": "7.1",
         "compiler.cppstd": "17"})
    be = AutotoolsToolchain(conanfile)
    env = be.vars()
    assert "-std=c++17" in env["CXXFLAGS"]

    # With visual
    conanfile.settings = MockSettings(
        {"build_type": "Release",
         "arch": "x86",
         "compiler": "Visual Studio",
         "compiler.version": "14",
         "compiler.cppstd": "17"})
    be = AutotoolsToolchain(conanfile)
    env = be.vars()
    assert "/std:c++latest" in env["CXXFLAGS"]


def test_fpic():
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"os": "Linux"})
    conanfile.options = MockOptions({"fPIC": True})
    be = AutotoolsToolchain(conanfile)
    be.vars()
    assert be.fpic is True
    assert "-fPIC" in be.cxxflags

    conanfile.options = MockOptions({"fPIC": False})
    be = AutotoolsToolchain(conanfile)
    be.vars()
    assert be.fpic is False
    assert "-fPIC" not in be.cxxflags

    conanfile.options = MockOptions({"shared": False})
    be = AutotoolsToolchain(conanfile)
    be.vars()
    assert be.fpic is None
    assert "-fPIC" not in be.cxxflags


def test_ndebug():
    conanfile = ConanFileMock()
    for bt in ['Release', 'RelWithDebInfo', 'MinSizeRel']:
        conanfile.settings = MockSettings({"build_type": bt})
        be = AutotoolsToolchain(conanfile)
        assert be.ndebug == "NDEBUG"
        env = be.vars()
        assert "-DNDEBUG" in env["CPPFLAGS"]
    for bt in ['Debug', 'DebWithDebInfo']:
        conanfile.settings = MockSettings({"build_type": bt})
        be = AutotoolsToolchain(conanfile)
        assert be.ndebug is None
        env = be.vars()
        assert "-DNDEBUG" not in env["CPPFLAGS"]


@pytest.mark.parametrize("config", [
    ("gcc", 'libstdc++', None),
    ("clang", 'libstdc++', '-stdlib=libstdc++'),
    ("clang", 'libstdc++11', '-stdlib=libstdc++'),
    ("clang", 'libc++', '-stdlib=libc++'),
    ("apple-clang", 'libstdc++', '-stdlib=libstdc++'),
    ("apple-clang", 'libstdc++11', '-stdlib=libstdc++'),
    ("apple-clang", 'libc++', '-stdlib=libc++'),
    ("sun-cc", 'libCstd', '-library=Cstd'),
    ("sun-cc", 'libstdcxx', '-library=stdcxx4'),
    ("sun-cc", 'libstlport', '-library=stlport4'),
    ("sun-cc", 'libstdc++', '-library=stdcpp'),
    ("qcc", 'libCstd', '-Y _libCstd'),
    ("qcc", 'libstdcxx', '-Y _libstdcxx'),
    ("qcc", 'libstlport', '-Y _libstlport'),
    ("qcc", 'libstdc++', '-Y _libstdc++'),
    ])
def test_libcxx(config):
    compiler, libcxx, expected_flag = config
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings(
        {"build_type": "Release",
         "arch": "x86",
         "compiler": compiler,
         "compiler.libcxx": libcxx,
         "compiler.version": "7.1",
         "compiler.cppstd": "17"})
    be = AutotoolsToolchain(conanfile)
    assert be.libcxx == expected_flag
    env = be.vars()
    if expected_flag:
        assert expected_flag in env["CXXFLAGS"]


def test_cxx11_abi_define():
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings(
        {"build_type": "Release",
         "arch": "x86",
         "compiler": "gcc",
         "compiler.libcxx": "libstdc++",
         "compiler.version": "7.1",
         "compiler.cppstd": "17"})
    be = AutotoolsToolchain(conanfile)
    assert be.gcc_cxx11_abi == "_GLIBCXX_USE_CXX11_ABI=0"
    env = be.vars()
    assert "-D_GLIBCXX_USE_CXX11_ABI=0" in env["CPPFLAGS"]

    conanfile.settings = MockSettings(
        {"build_type": "Release",
         "arch": "x86",
         "compiler": "gcc",
         "compiler.libcxx": "libstdc++11",
         "compiler.version": "7.1",
         "compiler.cppstd": "17"})
    be = AutotoolsToolchain(conanfile)
    env = be.vars()
    assert be.gcc_cxx11_abi is None
    assert "-D_GLIBCXX_USE_CXX11_ABI=0" not in env["CPPFLAGS"]


@pytest.mark.parametrize("config", [
    ('x86_64', "-m64"),
    ('x86', "-m32"),])
def test_architecture_flag(config):
    """Architecture flag is set in CXXFLAGS, CFLAGS and LDFLAGS"""
    arch, expected = config
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings(
        {"build_type": "Release",
         "os": "Macos",
         "compiler": "gcc",
         "arch": arch})
    be = AutotoolsToolchain(conanfile)
    assert be.arch_flag == expected
    env = be.vars()
    assert expected in env["CXXFLAGS"]
    assert expected in env["CFLAGS"]
    assert expected in env["LDFLAGS"]


def test_build_type_flag():
    """Architecture flag is set in CXXFLAGS, CFLAGS and LDFLAGS"""
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings(
        {"build_type": "Debug",
         "os": "Windows",
         "compiler": "Visual Studio",
         "arch": "x86_64"})
    be = AutotoolsToolchain(conanfile)
    assert be.build_type_flags == ["-Zi", "-Ob0", "-Od"]
    env = be.vars()
    assert "-Zi -Ob0 -Od" in env["CXXFLAGS"]
    assert "-Zi -Ob0 -Od" in env["CFLAGS"]
    assert "-Zi -Ob0 -Od" not in env["LDFLAGS"]


def test_apple_arch_flag():
    conanfile = ConanFileMock()
    conanfile.conf = {"tools.apple:sdk_path": "/path/to/sdk"}
    conanfile.settings_build = MockSettings(
        {"build_type": "Debug",
         "os": "Macos",
         "arch": "x86_64"})
    conanfile.settings = MockSettings(
        {"build_type": "Debug",
         "os": "iOS",
         "os.version": "14",
         "arch": "armv8"})
    be = AutotoolsToolchain(conanfile)
    expected = "-arch arm64"
    assert be.apple_arch_flag == expected
    env = be.vars()
    assert expected in env["CXXFLAGS"]
    assert expected in env["CFLAGS"]
    assert expected in env["LDFLAGS"]

    # Only set when crossbuilding
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings(
        {"build_type": "Debug",
         "os": "iOS",
         "os.version": "14",
         "arch": "armv8"})
    be = AutotoolsToolchain(conanfile)
    assert be.apple_arch_flag is None


def test_apple_min_os_flag():
    """Even when no cross building it is adjusted because it could target a Mac version"""
    conanfile = ConanFileMock()
    conanfile.conf = {"tools.apple:sdk_path": "/path/to/sdk"}
    conanfile.settings = MockSettings(
        {"build_type": "Debug",
         "os": "Macos",
         "os.version": "14",
         "arch": "armv8"})
    be = AutotoolsToolchain(conanfile)
    expected = "-mmacosx-version-min=14"
    assert be.apple_min_version_flag == expected
    env = be.vars()
    assert expected in env["CXXFLAGS"]
    assert expected in env["CFLAGS"]
    assert expected in env["LDFLAGS"]


def test_apple_isysrootflag():
    """Even when no cross building it is adjusted because it could target a Mac version"""
    conanfile = ConanFileMock()
    conanfile.conf = {"tools.apple:sdk_path": "/path/to/sdk"}
    conanfile.settings_build = MockSettings(
        {"build_type": "Debug",
         "os": "Macos",
         "arch": "x86_64"})
    conanfile.settings = MockSettings(
        {"build_type": "Debug",
         "os": "iOS",
         "os.version": "14",
         "arch": "armv8"})
    be = AutotoolsToolchain(conanfile)
    expected = "-isysroot /path/to/sdk"
    assert be.apple_isysroot_flag == expected
    env = be.vars()
    assert expected in env["CXXFLAGS"]
    assert expected in env["CFLAGS"]
    assert expected in env["LDFLAGS"]

    # Only set when crossbuilding
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings(
        {"build_type": "Debug",
         "os": "iOS",
         "os.version": "14",
         "arch": "armv8"})
    be = AutotoolsToolchain(conanfile)
    assert be.apple_isysroot_flag is None


def test_custom_defines():
    conanfile = ConanFileMock()
    conanfile.conf = {"tools.apple:sdk_path": "/path/to/sdk"}
    conanfile.settings = MockSettings(
        {"build_type": "RelWithDebInfo",
         "os": "iOS",
         "os.version": "14",
         "arch": "armv8"})
    be = AutotoolsToolchain(conanfile)
    be.defines = ["MyDefine1", "MyDefine2"]
    env = be.vars()
    assert "-DMyDefine1" in env["CPPFLAGS"]
    assert "-DMyDefine2" in env["CPPFLAGS"]
    assert "-DNDEBUG" in env["CPPFLAGS"]


def test_custom_cxxflags():
    conanfile = ConanFileMock()
    conanfile.conf = {"tools.apple:sdk_path": "/path/to/sdk"}
    conanfile.settings = MockSettings(
        {"build_type": "RelWithDebInfo",
         "os": "iOS",
         "os.version": "14",
         "arch": "armv8"})
    be = AutotoolsToolchain(conanfile)
    be.cxxflags = ["MyFlag1", "MyFlag2"]
    env = be.vars()
    assert "MyFlag1" in env["CXXFLAGS"]
    assert "MyFlag2" in env["CXXFLAGS"]
    assert "-mios-version-min=14" in env["CXXFLAGS"]

    assert "MyFlag" not in env["CFLAGS"]
    assert "MyFlag" not in env["LDFLAGS"]


def test_custom_cflags():
    conanfile = ConanFileMock()
    conanfile.conf = {"tools.apple:sdk_path": "/path/to/sdk"}
    conanfile.settings = MockSettings(
        {"build_type": "RelWithDebInfo",
         "os": "iOS",
         "os.version": "14",
         "arch": "armv8"})
    be = AutotoolsToolchain(conanfile)
    be.cflags = ["MyFlag1", "MyFlag2"]
    env = be.vars()
    assert "MyFlag1" in env["CFLAGS"]
    assert "MyFlag2" in env["CFLAGS"]
    assert "-mios-version-min=14" in env["CFLAGS"]

    assert "MyFlag" not in env["CXXFLAGS"]
    assert "MyFlag" not in env["LDFLAGS"]


def test_custom_ldflags():
    conanfile = ConanFileMock()
    conanfile.conf = {"tools.apple:sdk_path": "/path/to/sdk"}
    conanfile.settings = MockSettings(
        {"build_type": "RelWithDebInfo",
         "os": "iOS",
         "os.version": "14",
         "arch": "armv8"})
    be = AutotoolsToolchain(conanfile)
    be.ldflags = ["MyFlag1", "MyFlag2"]
    env = be.vars()
    assert "MyFlag1" in env["LDFLAGS"]
    assert "MyFlag2" in env["LDFLAGS"]
    assert "-mios-version-min=14" in env["LDFLAGS"]

    assert "MyFlag" not in env["CXXFLAGS"]
    assert "MyFlag" not in env["CFLAGS"]
