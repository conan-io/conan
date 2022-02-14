import pytest

from conan.tools.apple import XcodeBuild
from conans import Settings
from conans.errors import ConanException
from conans.model.conf import ConfDefinition
from conans.test.utils.mocks import ConanFileMock


@pytest.mark.parametrize("mode", ["quiet", "verbose", "invalid"])
def test_verbosity(mode):
    conanfile = ConanFileMock()
    conf = ConfDefinition()
    conf.loads("tools.apple.xcodebuild:verbosity={}".format(mode))
    conanfile.conf = conf
    conanfile.settings = Settings()
    xcodebuild = XcodeBuild(conanfile)
    if mode != "invalid":
        xcodebuild.build("app.xcodeproj")
        assert "-{}".format(mode) in conanfile.command
    else:
        with pytest.raises(ConanException) as excinfo:
            xcodebuild.build("app.xcodeproj")
        assert "Value {} for 'tools.apple.xcodebuild:verbosity' is not valid".format(mode) == str(excinfo.value)


def test_use_xcconfig():
    conanfile = ConanFileMock()
    conanfile.conf = ConfDefinition()
    conanfile.settings = Settings()
    xcodebuild = XcodeBuild(conanfile)
    xcodebuild.build("app.xcodeproj", use_xcconfig=False)
    assert "-xcconfig" not in conanfile.command
    xcodebuild.build("app.xcodeproj")
    assert "-xcconfig" in conanfile.command
