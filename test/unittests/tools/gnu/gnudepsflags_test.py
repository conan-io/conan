import pytest
from mock import MagicMock

from conan.tools.apple.apple import is_apple_os
from conan.tools.gnu.gnudeps_flags import GnuDepsFlags
from conan.test.utils.mocks import ConanFileMock, MockSettings


@pytest.mark.parametrize("os_", ["Macos", "Windows", "Linux"])
def test_framework_flags_only_for_apple_os(os_):
    """
    Testing GnuDepsFlags attributes exclusively for Apple OS, frameworks and framework_paths
    """
    # Issue: https://github.com/conan-io/conan/issues/10651
    # Issue: https://github.com/conan-io/conan/issues/10640
    settings = MockSettings({"build_type": "Release",
                             "compiler": "gcc",
                             "compiler.version": "10.2",
                             "os": os_,
                             "arch": "x86_64"})
    conanfile = ConanFileMock()
    conanfile.settings = settings
    cpp_info = MagicMock()
    cpp_info.frameworks = ["Foundation"]
    cpp_info.frameworkdirs = ["Framework"]
    gnudepsflags = GnuDepsFlags(conanfile, cpp_info)
    expected_framework = []
    expected_framework_path = []
    if is_apple_os(conanfile):
        expected_framework = ["-framework Foundation"]
        expected_framework_path = ["-F\"Framework\""]
    assert gnudepsflags.frameworks == expected_framework
    assert gnudepsflags.framework_paths == expected_framework_path
