import pytest

from conan.tools.apple.apple import _to_apple_arch, apple_min_version_flag, is_apple_os
from conan.test.utils.mocks import MockSettings, ConanFileMock


class TestApple:
    @pytest.mark.parametrize("os_, version, sdk, subsystem, flag",
                             [("Macos", "10.1", "macosx", None, '-mmacosx-version-min=10.1'),
                              ("iOS", "10.1", "iphoneos", None, '-mios-version-min=10.1'),
                              ("iOS", "10.1", "iphonesimulator", None,
                               '-mios-simulator-version-min=10.1'),
                              ("watchOS", "10.1", "watchos", None, '-mwatchos-version-min=10.1'),
                              ("watchOS", "10.1", "watchsimulator", None,
                               '-mwatchos-simulator-version-min=10.1'),
                              ("tvOS", "10.1", "appletvos", None, '-mtvos-version-min=10.1'),
                              ("tvOS", "10.1", "appletvsimulator", None,
                               '-mtvos-simulator-version-min=10.1'),
                              ("Macos", "10.1", "macosx", "catalyst", '-mios-version-min=10.1'),
                              ("Solaris", "10.1", None, None, ''),
                              ("Macos", "10.1", None, None, '-mmacosx-version-min=10.1'),
                              ("Macos", None, "macosx", None, '')
                              ])
    def test_deployment_target_flag_name(self, os_, version, sdk, subsystem, flag):
        conanfile = ConanFileMock()
        settings = MockSettings({"os": os_,
                                 "os.version": version,
                                 "os.sdk": sdk,
                                 "os.subsystem": subsystem})
        conanfile.settings = settings
        assert apple_min_version_flag(conanfile) == flag

    @pytest.mark.parametrize("_os, result",
                             [("Macos", True), ("iOS", True), ("tvOS", True), ("watchOS", True),
                              ("Linux", False), ("Windows", False), ("Android", False)])
    def test_is_apple_os(self, _os, result):
        conanfile = ConanFileMock()
        settings = MockSettings({"os": _os})
        conanfile.settings = settings
        assert is_apple_os(conanfile) == result

    def test_to_apple_arch(self):
        assert _to_apple_arch('x86') == 'i386'
        assert _to_apple_arch('x86_64') == 'x86_64'
        assert _to_apple_arch('armv7') == 'armv7'
        assert _to_apple_arch('armv7s') == 'armv7s'
        assert _to_apple_arch('armv7k') == 'armv7k'
        assert _to_apple_arch('armv8') == 'arm64'
        assert _to_apple_arch('armv8.3') == 'arm64e'
        assert _to_apple_arch('armv8_32') == 'arm64_32'
        assert _to_apple_arch('mips') is None
        assert _to_apple_arch('mips', default='mips') == 'mips'
