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


@pytest.mark.parametrize("os_name, os_version, expected_key", [
    ("Macos", "14.0", "MACOSX_DEPLOYMENT_TARGET"),
    ("iOS", "15.1", "IPHONEOS_DEPLOYMENT_TARGET"),
    ("watchOS", "8.0", "WATCHOS_DEPLOYMENT_TARGET"),
    ("tvOS", "15.0", "TVOS_DEPLOYMENT_TARGET"),
    ("visionOS", "1.0", "XROS_DEPLOYMENT_TARGET")
])
def test_deployment_target_and_quoting(os_name, os_version, expected_key):
    """
    Checks that the correct deployment target is passed and that paths are quoted.
    """
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"os": os_name, "os.version": os_version})
    xcodebuild = XcodeBuild(conanfile)

    xcodebuild.build("My Project.xcodeproj", target="My Target")

    expected_arg = f" {expected_key}={os_version}"
    assert expected_arg in conanfile.command

    assert "-project 'My Project.xcodeproj'" in conanfile.command
    assert "-target 'My Target'" in conanfile.command


def test_no_deployment_target_if_version_is_missing():
    """
    Checks that the deployment target argument is not added if os.version is missing.
    """
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"os": "Macos"})
    xcodebuild = XcodeBuild(conanfile)
    xcodebuild.build("app.xcodeproj")

    assert "MACOSX_DEPLOYMENT_TARGET" not in conanfile.command
