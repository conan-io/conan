import pytest

from conan.tools.apple import XcodeBuild
from conans.errors import ConanException
from conans.model.conf import ConfDefinition
from conans.test.utils.mocks import ConanFileMock, MockSettings


@pytest.mark.parametrize("mode", ["quiet", "verbose", "invalid"])
def test_verbosity(mode):
    conanfile = ConanFileMock()
    conf = ConfDefinition()
    conf.loads("tools.apple.xcodebuild:verbosity={}".format(mode))
    conanfile.conf = conf
    conanfile.settings = MockSettings({})
    xcodebuild = XcodeBuild(conanfile)
    if mode != "invalid":
        xcodebuild.build("app.xcodeproj")
        assert "-{}".format(mode) in conanfile.command
    else:
        with pytest.raises(ConanException) as excinfo:
            xcodebuild.build("app.xcodeproj")
        assert "Value {} for 'tools.apple.xcodebuild:verbosity' is not valid".format(mode) == str(
            excinfo.value)


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
