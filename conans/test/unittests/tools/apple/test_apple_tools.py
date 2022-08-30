from conans.test.utils.mocks import ConanFileMock, MockSettings
from conan.tools.apple import is_apple_os, to_apple_arch

def test_tools_apple_is_apple_os():
    conanfile = ConanFileMock()
    
    conanfile.settings = MockSettings({"os": "Macos"})
    assert is_apple_os(conanfile) == True

    conanfile.settings = MockSettings({"os": "watchOS"})
    assert is_apple_os(conanfile) == True

    conanfile.settings = MockSettings({"os": "Windows"})
    assert is_apple_os(conanfile) == False

    
def test_tools_apple_to_apple_arch():
    conanfile = ConanFileMock()
    
    conanfile.settings = MockSettings({"arch": "armv8"})
    assert to_apple_arch(conanfile) == "arm64"

    conanfile.settings = MockSettings({"arch": "x86_64"})
    assert to_apple_arch(conanfile) == "x86_64"
