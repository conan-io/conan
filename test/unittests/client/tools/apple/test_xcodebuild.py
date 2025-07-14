import pytest

from conan.tools.apple import XcodeBuild
from conan.internal.model.conf import ConfDefinition
from conan.test.utils.mocks import ConanFileMock, MockSettings


@pytest.mark.parametrize("mode", ["quiet", None, "verbose"])
def test_verbosity_global(mode):
    conanfile = ConanFileMock()
    conf = ConfDefinition()
    if mode is not None:
        conf.loads(f"tools.build:verbosity={mode}")
    conanfile.conf = conf
    conanfile.settings = MockSettings({})
    xcodebuild = XcodeBuild(conanfile)

    xcodebuild.build("app.xcodeproj")
    if mode == "verbose":
        assert "-verbose" in conanfile.command
        assert "-quiet" not in conanfile.command
    elif mode == "quiet":
        assert "-verbose" not in conanfile.command
        assert "-quiet" in conanfile.command
    else:
        assert "-verbose" not in conanfile.command
        assert "-quiet" not in conanfile.command


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
