import platform

import pytest

from conan.test.utils.mocks import ConanFileMock
from conan.tools.google import Bazel, BazelToolchain
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


def test_bazel_skips_rc_when_workspace_imports_it(tmp_path):
    conanfile = ConanFileMock()
    conanfile.folders.set_base_generators(str(tmp_path))
    conanfile.folders.set_base_source(str(tmp_path))
    conanfile.folders.set_base_build(str(tmp_path))
    tmp_path.joinpath(BazelToolchain.bazelrc_name).write_text("", encoding="utf-8")
    tmp_path.joinpath(".bazelrc").write_text(
        "try-import %workspace%/conan/conan_bzl.rc\n", encoding="utf-8")
    conanfile.conf.define("tools.google.bazel:bazelrc_path", ["/path/to/bazelrc"])
    bazel = Bazel(conanfile)
    bazel.build(target="//test:label", clean=False)
    command = next(cmd for cmd in conanfile._commands if " build " in cmd)
    assert "--config=conan-config" in command
    assert "--bazelrc=/path/to/bazelrc" in command
    assert BazelToolchain.bazelrc_name not in command


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
