import platform
from os import chdir

import pytest

from conan.tools.files.files import load_toolchain_args
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
    conanfile.conf.define("tools.gnu:make_program", "my_make")
    conanfile.conf.define("tools.gnu.make:jobs", "23")

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

def test_custom_host_triple():
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"os": "Linux", "arch": "x86"})
    conanfile.settings_build = MockSettings({"os": "Linux", "arch": "x86_64"})
    conanfile.conf.define("tools.gnu:host_triplet", "i686-pc-linux-gnu")
    tc = AutotoolsToolchain(conanfile)
    tc.generate_args()
    obj = load_toolchain_args()
    assert "--host=i686-pc-linux-gnu" in obj["configure_args"]

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
    conanfile.settings_build = MockSettings({"os": "Linux", "arch": "x86"})
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
         "compiler": "msvc",
         "compiler.version": "190",
         "compiler.cppstd": "17"})
    be = AutotoolsToolchain(conanfile)
    env = be.vars()
    assert "/std:c++latest" in env["CXXFLAGS"]

    # With MSVC
    conanfile.settings = MockSettings(
        {"build_type": "Release",
         "arch": "x86",
         "compiler": "msvc",
         "compiler.version": "193",
         "compiler.cppstd": "17"})
    be = AutotoolsToolchain(conanfile)
    env = be.vars()
    assert "/std:c++17" in env["CXXFLAGS"]


def test_fpic():
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"os": "Linux"})
    conanfile.settings_build = MockSettings({"os": "Linux"})
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
        conanfile.settings_build = MockSettings({"os": "Linux", "arch": "x86_64"})
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
    the_os = "Linux" if compiler != "apple-clang" else "Macos"
    conanfile.settings = MockSettings(
        {"os": the_os,
         "build_type": "Release",
         "arch": "x86",
         "compiler": compiler,
         "compiler.libcxx": libcxx,
         "compiler.version": "7.1",
         "compiler.cppstd": "17"})
    conanfile.settings_build = conanfile.settings
    be = AutotoolsToolchain(conanfile)
    assert be.libcxx == expected_flag
    env = be.vars()
    if expected_flag:
        assert expected_flag in env["CXXFLAGS"]


def test_cxx11_abi_define():
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings(
        {"os": "Linux",
         "build_type": "Release",
         "arch": "x86",
         "compiler": "gcc",
         "compiler.libcxx": "libstdc++",
         "compiler.version": "7.1",
         "compiler.cppstd": "17"})
    conanfile.settings_build = conanfile.settings
    be = AutotoolsToolchain(conanfile)
    assert be.gcc_cxx11_abi == "_GLIBCXX_USE_CXX11_ABI=0"
    env = be.vars()
    assert "-D_GLIBCXX_USE_CXX11_ABI=0" in env["CPPFLAGS"]

    conanfile.settings = MockSettings(
        {"os": "Linux",
         "build_type": "Release",
         "arch": "x86",
         "compiler": "gcc",
         "compiler.libcxx": "libstdc++11",
         "compiler.version": "7.1",
         "compiler.cppstd": "17"})
    be = AutotoolsToolchain(conanfile)
    env = be.vars()
    assert be.gcc_cxx11_abi is None
    assert "GLIBCXX_USE_CXX11_ABI" not in env["CPPFLAGS"]

    # Force the GLIBCXX_USE_CXX11_ABI=1 for old distros is direct def f ``gcc_cxx11_abi``
    be.gcc_cxx11_abi = "_GLIBCXX_USE_CXX11_ABI=1"
    env = be.vars()
    assert "-D_GLIBCXX_USE_CXX11_ABI=1" in env["CPPFLAGS"]

    # Also conf is possible
    conanfile.conf.define("tools.gnu:define_libcxx11_abi", True)
    be = AutotoolsToolchain(conanfile)
    env = be.vars()
    assert "-D_GLIBCXX_USE_CXX11_ABI=1" in env["CPPFLAGS"]


@pytest.mark.parametrize("config", [
    ('x86_64', "-m64"),
    ('x86', "-m32")])
def test_architecture_flag(config):
    """Architecture flag is set in CXXFLAGS, CFLAGS and LDFLAGS"""
    arch, expected = config
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings(
        {"build_type": "Release",
         "os": "Macos",
         "compiler": "gcc",
         "arch": arch})
    conanfile.settings_build = conanfile.settings
    be = AutotoolsToolchain(conanfile)
    assert be.arch_flag == expected
    env = be.vars()
    assert expected in env["CXXFLAGS"]
    assert expected in env["CFLAGS"]
    assert expected in env["LDFLAGS"]
    assert "-debug" not in env["LDFLAGS"]


@pytest.mark.parametrize("compiler", ['msvc'])
def test_build_type_flag(compiler):
    """Architecture flag is set in CXXFLAGS, CFLAGS and LDFLAGS"""
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings(
        {"build_type": "Debug",
         "os": "Windows",
         "compiler": compiler,
         "arch": "x86_64"})
    conanfile.settings_build = conanfile.settings
    be = AutotoolsToolchain(conanfile)
    assert be.build_type_flags == ["-Zi", "-Ob0", "-Od"]
    env = be.vars()
    assert "-Zi -Ob0 -Od" in env["CXXFLAGS"]
    assert "-Zi -Ob0 -Od" in env["CFLAGS"]
    assert "-Zi -Ob0 -Od" not in env["LDFLAGS"]
    assert "-debug" in env["LDFLAGS"]


def test_apple_arch_flag():
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.apple:sdk_path", "/path/to/sdk")
    conanfile.settings_build = MockSettings(
        {"build_type": "Debug",
         "os": "Macos",
         "arch": "x86_64"})
    conanfile.settings = MockSettings(
        {"build_type": "Debug",
         "os": "iOS",
         "os.version": "14",
         "os.sdk": "iphoneos",
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
    conanfile.conf = {"tools.apple:sdk_path": "/path/to/sdk"}
    conanfile.settings = MockSettings(
        {"build_type": "Debug",
         "os": "Macos",
         "os.version": "14",
         "arch": "x86_64"})
    conanfile.settings_build = MockSettings({"os": "Macos", "arch": "x86_64"})
    be = AutotoolsToolchain(conanfile)
    assert be.apple_arch_flag is None


def test_apple_min_os_flag():
    """Even when no cross building it is adjusted because it could target a Mac version"""
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.apple:sdk_path", "/path/to/sdk")
    conanfile.settings = MockSettings(
        {"build_type": "Debug",
         "os": "Macos",
         "os.version": "14",
         "arch": "armv8"})
    conanfile.settings_build = MockSettings({"os": "Macos", "arch": "armv8"})
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
    conanfile.conf.define("tools.apple:sdk_path", "/path/to/sdk")
    conanfile.settings_build = MockSettings(
        {"build_type": "Debug",
         "os": "Macos",
         "arch": "x86_64"})
    conanfile.settings = MockSettings(
        {"build_type": "Debug",
         "os": "iOS",
         "os.sdk": "iphoneos",
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
    conanfile.conf = {"tools.apple:sdk_path": "/path/to/sdk"}
    conanfile.settings = MockSettings(
        {"build_type": "Debug",
         "os": "Macos",
         "os.version": "14",
         "arch": "armv8"})
    conanfile.settings_build = MockSettings(
        {"build_type": "Debug",
         "os": "Macos",
         "os.version": "14",
         "arch": "armv8"})
    be = AutotoolsToolchain(conanfile)
    assert be.apple_isysroot_flag is None


def test_sysrootflag():
    """Even when no cross building it is adjusted because it could target a Mac version"""
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.build:sysroot", "/path/to/sysroot")
    conanfile.settings = MockSettings(
        {"build_type": "Debug",
         "os": {"Darwin": "Macos"}.get(platform.system(), platform.system()),
         "arch": "x86_64"})
    conanfile.settings_build = conanfile.settings
    be = AutotoolsToolchain(conanfile)
    expected = "--sysroot /path/to/sysroot"
    assert be.sysroot_flag == expected
    env = be.vars()
    assert expected in env["CXXFLAGS"]
    assert expected in env["CFLAGS"]
    assert expected in env["LDFLAGS"]


def test_custom_defines():
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.apple:sdk_path", "/path/to/sdk")
    conanfile.settings = MockSettings(
        {"build_type": "RelWithDebInfo",
         "os": "iOS",
         "os.sdk": "iphoneos",
         "os.version": "14",
         "arch": "armv8"})
    conanfile.settings_build = MockSettings({"os": "Macos", "arch": "armv8"})
    be = AutotoolsToolchain(conanfile)
    be.extra_defines = ["MyDefine1", "MyDefine2"]

    assert "MyDefine1" in be.defines
    assert "MyDefine2" in be.defines
    assert "NDEBUG" in be.defines

    env = be.vars()
    assert "-DMyDefine1" in env["CPPFLAGS"]
    assert "-DMyDefine2" in env["CPPFLAGS"]
    assert "-DNDEBUG" in env["CPPFLAGS"]


def test_custom_cxxflags():
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.apple:sdk_path", "/path/to/sdk")
    conanfile.settings = MockSettings(
        {"build_type": "RelWithDebInfo",
         "os": "iOS",
         "os.sdk": "iphoneos",
         "os.version": "14",
         "arch": "armv8"})
    conanfile.settings_build = MockSettings({"os": "Macos", "arch": "armv8"})
    be = AutotoolsToolchain(conanfile)
    be.extra_cxxflags = ["MyFlag1", "MyFlag2"]

    assert "MyFlag1" in be.cxxflags
    assert "MyFlag2" in be.cxxflags
    assert "-mios-version-min=14" in be.cxxflags
    assert "MyFlag" not in be.cflags
    assert "MyFlag" not in be.ldflags

    env = be.vars()
    assert "MyFlag1" in env["CXXFLAGS"]
    assert "MyFlag2" in env["CXXFLAGS"]
    assert "-mios-version-min=14" in env["CXXFLAGS"]

    assert "MyFlag" not in env["CFLAGS"]
    assert "MyFlag" not in env["LDFLAGS"]


def test_custom_cflags():
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.apple:sdk_path", "/path/to/sdk")
    conanfile.settings = MockSettings(
        {"build_type": "RelWithDebInfo",
         "os": "iOS",
         "os.sdk": "iphoneos",
         "os.version": "14",
         "arch": "armv8"})
    conanfile.settings_build = MockSettings({"os": "Macos", "arch": "armv8"})
    be = AutotoolsToolchain(conanfile)
    be.extra_cflags = ["MyFlag1", "MyFlag2"]

    assert "MyFlag1" in be.cflags
    assert "MyFlag2" in be.cflags
    assert "-mios-version-min=14" in be.cflags
    assert "MyFlag" not in be.cxxflags
    assert "MyFlag" not in be.ldflags

    env = be.vars()
    assert "MyFlag1" in env["CFLAGS"]
    assert "MyFlag2" in env["CFLAGS"]
    assert "-mios-version-min=14" in env["CFLAGS"]

    assert "MyFlag" not in env["CXXFLAGS"]
    assert "MyFlag" not in env["LDFLAGS"]


def test_custom_ldflags():
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.apple:sdk_path", "/path/to/sdk")
    conanfile.settings = MockSettings(
        {"build_type": "RelWithDebInfo",
         "os": "iOS",
         "os.sdk": "iphoneos",
         "os.version": "14",
         "arch": "armv8"})
    conanfile.settings_build = MockSettings({"os": "Macos", "arch": "armv8"})
    be = AutotoolsToolchain(conanfile)
    be.extra_ldflags = ["MyFlag1", "MyFlag2"]

    assert "MyFlag1" in be.ldflags
    assert "MyFlag2" in be.ldflags
    assert "-mios-version-min=14" in be.ldflags
    assert "MyFlag" not in be.cxxflags
    assert "MyFlag" not in be.cflags

    env = be.vars()
    assert "MyFlag1" in env["LDFLAGS"]
    assert "MyFlag2" in env["LDFLAGS"]
    assert "-mios-version-min=14" in env["LDFLAGS"]

    assert "MyFlag" not in env["CXXFLAGS"]
    assert "MyFlag" not in env["CFLAGS"]


def test_extra_flags_via_conf():
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.build:cxxflags", ["--flag1", "--flag2"])
    conanfile.conf.define("tools.build:cflags", ["--flag3", "--flag4"])
    conanfile.conf.define("tools.build:sharedlinkflags", ["--flag5"])
    conanfile.conf.define("tools.build:exelinkflags", ["--flag6"])
    conanfile.conf.define("tools.build:defines", ["DEF1", "DEF2"])
    conanfile.settings = MockSettings(
        {"build_type": "RelWithDebInfo",
         "os": "iOS",
         "os.sdk": "iphoneos",
         "os.version": "14",
         "arch": "armv8"})
    conanfile.settings_build = MockSettings({"os": "iOS", "arch": "armv8"})
    be = AutotoolsToolchain(conanfile)
    env = be.vars()
    assert '-DNDEBUG -DDEF1 -DDEF2' in env["CPPFLAGS"]
    assert '-mios-version-min=14 --flag1 --flag2' in env["CXXFLAGS"]
    assert '-mios-version-min=14 --flag3 --flag4' in env["CFLAGS"]
    assert '-mios-version-min=14 --flag5 --flag6' in env["LDFLAGS"]
