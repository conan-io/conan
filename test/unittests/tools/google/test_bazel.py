import platform

import pytest

from conan.test.utils.mocks import ConanFileMock
from conan.tools.google import Bazel
from conan.tools.google.bazeldeps import _relativize_path


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
