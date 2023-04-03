import pytest

from conan.tools.apple import XcodeBuild
from conans.errors import ConanException
from conans.model.conf import ConfDefinition
from conans.test.utils.mocks import ConanFileMock, MockSettings


@pytest.mark.parametrize("mode", ["quiet", "error", "warning", "notice", "status", "verbose",
                                  "normal", "debug", "v", "trace", "vv"])
def test_verbosity_global(mode):
    conanfile = ConanFileMock()
    conf = ConfDefinition()
    conf.loads(f"tools.build:verbosity={mode}")
    conanfile.conf = conf
    conanfile.settings = MockSettings({})
    xcodebuild = XcodeBuild(conanfile)

    xcodebuild.build("app.xcodeproj")
    if mode not in ("status", "verbose", "normal"):
        assert "-quiet" in conanfile.command or "-verbose" in conanfile.command
    else:
        assert "-quiet" not in conanfile.command and "-verbose" not in conanfile.command


def test_sdk_path():
    conanfile = ConanFileMock()
    conf = ConfDefinition()
    conf.loads("tools.apple:sdk_path=mypath")
    conanfile.conf = conf
    conanfile.settings = MockSettings({})
    xcodebuild = XcodeBuild(conanfile)
    xcodebuild.build("app.xcodeproj")
    assert "SDKROOT=mypath " in conanfile.command


def test_sdk():
    conanfile = ConanFileMock()
    conf = ConfDefinition()
    conf.loads("tools.apple:sdk_path=mypath")
    conanfile.conf = conf
    conanfile.settings = MockSettings({"os": "Macos",
                                       "os.sdk": "macosx"})
    xcodebuild = XcodeBuild(conanfile)
    xcodebuild.build("app.xcodeproj")
    # sdk_path takes preference
    assert "SDKROOT=mypath " in conanfile.command
    conf = ConfDefinition()
    conanfile.conf = conf
    xcodebuild = XcodeBuild(conanfile)
    xcodebuild.build("app.xcodeproj")
    assert "SDKROOT=macosx " in conanfile.command
    conanfile.settings = MockSettings({"os": "Macos",
                                       "os.sdk": "macosx",
                                       "os.sdk_version": "12.1"})
    xcodebuild = XcodeBuild(conanfile)
    xcodebuild.build("app.xcodeproj")
    assert "SDKROOT=macosx12.1 " in conanfile.command
    conanfile.settings = MockSettings({})
    xcodebuild = XcodeBuild(conanfile)
    xcodebuild.build("app.xcodeproj")
    assert "SDKROOT" not in conanfile.command
