import os
import platform
from unittest.mock import MagicMock

import pytest

from conan.test.utils.mocks import ConanFileMock
from conan.test.utils.test_files import temp_folder
from conan.tools.files import save
from conan.tools.google import Bazel
from conan.tools.google.bazeldeps import _relativize_path


@pytest.fixture(scope="module")
def cpp_info():
    folder = temp_folder(path_with_spaces=False)
    bindirs = os.path.join(folder, "bin")
    libdirs = os.path.join(folder, "lib")
    save(ConanFileMock(), os.path.join(bindirs, "mylibwin.dll"), "")
    save(ConanFileMock(), os.path.join(bindirs, "mylibwin2.dll"), "")
    save(ConanFileMock(), os.path.join(bindirs, "myliblin.so"), "")
    save(ConanFileMock(), os.path.join(bindirs, "mylibmac.dylib"), "")
    save(ConanFileMock(), os.path.join(bindirs, "protoc"), "")  # binary
    save(ConanFileMock(), os.path.join(libdirs, "myliblin.a"), "")
    save(ConanFileMock(), os.path.join(libdirs, "mylibmac.a"), "")
    save(ConanFileMock(), os.path.join(libdirs, "mylibwin.lib"), "")
    save(ConanFileMock(), os.path.join(libdirs, "mylibwin2.if.lib"), "")
    save(ConanFileMock(), os.path.join(libdirs, "libmylib.so"), "")
    save(ConanFileMock(), os.path.join(libdirs, "subfolder", "libmylib.a"), "")  # recursive
    cpp_info_mock = MagicMock(_base_folder=None, libdirs=[], bindirs=[], libs=[],
                              aggregated_components=MagicMock())
    cpp_info_mock._base_folder = folder.replace("\\", "/")
    cpp_info_mock.libdirs = [libdirs]
    cpp_info_mock.bindirs = [bindirs]
    cpp_info_mock.aggregated_components.return_value = cpp_info_mock
    return cpp_info_mock


@pytest.mark.skipif(platform.system() == "Windows", reason="Remove this skip for Conan 2.x"
                                                           "Needs conanfile.commands")
def test_bazel_command_with_empty_config():
    conanfile = ConanFileMock()
    bazel = Bazel(conanfile)
    bazel.build(target='//test:label')
    # Uncomment Conan 2.x
    assert 'bazel build //test:label' in conanfile.commands


@pytest.mark.skipif(platform.system() == "Windows", reason="Remove this skip for Conan 2.x."
                                                           "Needs conanfile.commands")
def test_bazel_command_with_config_values():
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.google.bazel:configs", ["config", "config2"])
    conanfile.conf.define("tools.google.bazel:bazelrc_path", ["/path/to/bazelrc"])
    bazel = Bazel(conanfile)
    bazel.build(target='//test:label')
    commands = conanfile.commands
    assert "bazel --bazelrc=/path/to/bazelrc build " \
           "--config=config --config=config2 //test:label" in commands
    assert "bazel --bazelrc=/path/to/bazelrc clean" in commands


@pytest.mark.parametrize("path, pattern, expected", [
    ("", "./", ""),
    ("./", "", "./"),
    ("/my/path/", "", "/my/path/"),
    ("\\my\\path\\", "", "\\my\\path\\"),
    ("/my/path/absolute", ".*/path", "absolute"),
    ("/my/path/absolute", "/my/path", "absolute"),
    ("\\my\\path\\absolute", "/my/path", "absolute"),
    ("/my/./path/absolute/", "/my/./path", "absolute"),
    ("/my/./path/absolute/", "/my/./path/absolute/", "./"),
    ("././my/path/absolute/././", "./", "my/path/absolute"),
    ("C:\\my\\path\\absolute\\with\\folder", "C:\\", "my/path/absolute/with/folder"),
    ("C:\\my\\path\\absolute\\with\\folder", ".*/absolute", "with/folder"),
    ("C:\\my\\path\\myabsolute\\with\\folder", ".*/absolute", "C:\\my\\path\\myabsolute\\with\\folder"),
])
def test_bazeldeps_relativize_path(path, pattern, expected):
    assert _relativize_path(path, pattern) == expected
