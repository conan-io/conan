import os
import platform

import pytest

from conan.tools.apple.apple import XCRun
from conan.test.utils.mocks import ConanFileMock, MockSettings
from conans.util.runners import conan_run


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires OSX and xcrun tool")
def test_xcrun():
    def _common_asserts(xcrun_):
        assert xcrun_.cc.endswith('clang')
        assert xcrun_.cxx.endswith('clang++')
        assert xcrun_.ar.endswith('ar')
        assert xcrun_.ranlib.endswith('ranlib')
        assert xcrun_.strip.endswith('strip')
        assert xcrun_.find('lipo').endswith('lipo')
        assert os.path.isdir(xcrun_.sdk_path)

    conanfile = ConanFileMock( runner=conan_run)
    conanfile.settings = MockSettings(
        {"os": "Macos",
         "arch": "x86"})
    xcrun = XCRun(conanfile)
    _common_asserts(xcrun)

    conanfile.settings = MockSettings(
        {"os": "iOS",
         "arch": "x86"})
    xcrun = XCRun(conanfile, sdk='macosx')
    _common_asserts(xcrun)
    # Simulator
    assert "iPhoneOS" not in xcrun.sdk_path

    conanfile.settings = MockSettings(
        {"os": "iOS",
         "os.sdk": "iphoneos",
         "arch": "armv7"})
    xcrun = XCRun(conanfile)
    _common_asserts(xcrun)
    assert "iPhoneOS" in xcrun.sdk_path

    conanfile.settings = MockSettings(
        {"os": "watchOS",
         "os.sdk": "watchos",
         "arch": "armv7"})
    xcrun = XCRun(conanfile)
    _common_asserts(xcrun)
    assert "WatchOS" in xcrun.sdk_path

    # Default one
    conanfile.settings = MockSettings({})
    xcrun = XCRun(conanfile)
    _common_asserts(xcrun)
