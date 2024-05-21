from conan.test.utils.mocks import ConanFileMock, MockSettings
from conans.errors import ConanException
from conan.tools.android import android_abi

from pytest import raises


def test_tools_android_abi():
    settings_linux = MockSettings({"os": "Linux", "arch": "foo"})

    for (arch, expected) in [
        ("armv5el", "armeabi"),
        ("armv5hf", "armeabi"),
        ("armv5", "armeabi"),
        ("armv6", "armeabi-v6"),
        ("armv7", "armeabi-v7a"),
        ("armv7hf", "armeabi-v7a"),
        ("armv8", "arm64-v8a"),
        ("x86", "x86"),
        ("x86_64", "x86_64"),
        ("mips", "mips"),
        ("mips_64", "mips_64"),
    ]:
        conanfile = ConanFileMock()
        settings_android = MockSettings({"os": "Android", "arch": arch})

        # 2 profiles
        ## native build
        conanfile.settings = settings_android
        conanfile.settings_host = settings_android
        conanfile.settings_build = settings_android

        assert android_abi(conanfile) == expected
        assert android_abi(conanfile, context="host") == expected
        assert android_abi(conanfile, context="build") == expected

        with raises(ConanException):
            assert android_abi(conanfile, context="target") == expected

        ## cross-build from Android to Linux (quite hypothetical)
        conanfile.settings = settings_linux
        conanfile.settings_host = settings_linux
        conanfile.settings_build = settings_android
        assert android_abi(conanfile) != expected
        assert android_abi(conanfile, context="host") != expected
        assert android_abi(conanfile, context="build") == expected

        with raises(ConanException):
            assert android_abi(conanfile, context="target")

        ## cross-build a recipe from Linux to Android:
        ### test android_abi in recipe itself
        conanfile.settings = settings_android
        conanfile.settings_host = settings_android
        conanfile.settings_build = settings_linux
        assert android_abi(conanfile) == expected
        assert android_abi(conanfile, context="host") == expected
        assert android_abi(conanfile, context="build") != expected
        with raises(ConanException):
            android_abi(conanfile, context="target")

        ### test android_abi in "compiler recipe" (ie a android-ndk recipe in tool_requires of recipe being cross-build)
        conanfile.settings = settings_linux
        conanfile.settings_host = settings_linux
        conanfile.settings_build = settings_linux
        conanfile.settings_target = settings_android
        assert android_abi(conanfile) != expected
        assert android_abi(conanfile, context="host") != expected
        assert android_abi(conanfile, context="build") != expected
        assert android_abi(conanfile, context="target") == expected
