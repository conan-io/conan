import pytest
from conan.tools.gnu.helpers import is_mingw
from conan.test.utils.mocks import ConanFileMock, MockSettings

def test_is_mingw():
    # Test True
    settings = MockSettings({"os": "Windows", "compiler": "gcc"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    assert is_mingw(conanfile) is True

    settings.values["compiler"] = "clang"
    assert is_mingw(conanfile) is True

    # Test False
    settings.values["compiler"] = "msvc"
    assert is_mingw(conanfile) is False

    settings.values["os"] = "Linux"
    settings.values["compiler"] = "gcc"
    assert is_mingw(conanfile) is False

