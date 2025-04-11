import textwrap

import pytest

from conan.tools.meson import Meson
from conan.internal.model.conf import ConfDefinition
from conan.test.utils.mocks import ConanFileMock, MockSettings
from conan.tools.meson.helpers import get_apple_subsystem


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
