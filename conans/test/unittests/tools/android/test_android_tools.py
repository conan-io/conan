from conans.test.utils.mocks import ConanFileMock, MockSettings
from conan.tools.android import android_abi


def test_tools_android_abi():
    settings_linux = MockSettings({"os": "Linux", "arch": "x86_64"})

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

        conanfile.settings = settings_android
        assert android_abi(conanfile) == expected
        assert android_abi(conanfile, context="host") == expected
        assert android_abi(conanfile, context="build") == expected
        assert android_abi(conanfile, context="target") == expected

        conanfile.settings = settings_linux
        conanfile.settings_build = settings_android
        assert android_abi(conanfile, context="build") == expected

        conanfile.settings_build = settings_linux
        conanfile.settings_target = settings_android
        assert android_abi(conanfile, context="target") == expected
