import textwrap

import pytest

from conan.tools.meson import Meson
from conan.internal.model.conf import ConfDefinition
from conan.test.utils.mocks import ConanFileMock, MockSettings
from conan.tools.meson.helpers import get_apple_subsystem, to_cstd_flag, to_cppstd_flag


def test_meson_build():
    c = ConfDefinition()
    c.loads(textwrap.dedent("""\
        tools.build:jobs=10
    """))

    settings = MockSettings({"build_type": "Release",
                             "compiler": "gcc",
                             "compiler.version": "7",
                             "os": "Linux",
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    conanfile.display_name = 'test'
    conanfile.conf = c.get_conanfile_conf(None)

    meson = Meson(conanfile)
    meson.build()

    assert '-j10' in str(conanfile.command)


@pytest.mark.parametrize("apple_sdk, subsystem", [
    ("iphoneos", "ios"),
    ("iphonesimulator", "ios-simulator"),
    ("appletvos", "tvos"),
    ("appletvsimulator", "tvos-simulator"),
    ("watchos", "watchos"),
    ("watchsimulator", "watchos-simulator"),
    (None, "macos")
])
def test_meson_subsystem_helper(apple_sdk, subsystem):
    assert get_apple_subsystem(apple_sdk) == subsystem


@pytest.mark.parametrize("cstd, expected", [
    ("gnu23", "gnu23"),
    ("23", "c23"),
    (None, None)
])
def test_meson_to_cstd_flag(cstd, expected):
    assert to_cstd_flag(cstd) == expected


@pytest.mark.parametrize("compiler, compiler_version, cppstd, expected", [
    ("gcc", "14.0", "26", "c++26"),
    ("gcc", "14.0", "gnu26", "gnu++26"),
    ("gcc", "14.0", "gnu23", "gnu++23"),
    ("gcc", "14.0", "23", "c++23"),
    ("gcc", "15.0", "26", "c++26"),
    ("msvc", "193", "23", "vc++latest"),
    (None, None, "26", "c++26"),
    (None, None, None, None)
])
def test_meson_to_cppstd_flag(compiler, compiler_version, cppstd, expected):
    assert to_cppstd_flag(compiler, compiler_version, cppstd) == expected
