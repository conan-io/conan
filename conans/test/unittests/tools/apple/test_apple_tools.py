import pytest

from conans.test.utils.mocks import ConanFileMock, MockSettings
from conans.test.utils.test_files import temp_folder
from conan.tools.apple import is_apple_os, to_apple_arch, fix_apple_shared_install_name

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

def test_fix_shared_install_name_no_libraries():
    conanfile = ConanFileMock(
        options="""{"shared": [True, False]}""",
        options_values={"shared": True})
    conanfile.settings = MockSettings({"os": "Macos"})
    conanfile.folders.set_base_package(temp_folder())

    with pytest.raises(Exception) as e:
        fix_apple_shared_install_name(conanfile)
        assert "not found inside package folder" in str(e.value)
