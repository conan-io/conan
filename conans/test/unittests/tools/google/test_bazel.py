import platform

import pytest

from conan.tools.google import Bazel
from conans.test.utils.mocks import ConanFileMock


@pytest.mark.skipif(platform.system() == "Windows", reason="Remove this skip for Conan 2.x"
                                                           "Needs conanfile.commands")
def test_bazel_command_with_empty_config():
    conanfile = ConanFileMock()
    bazel = Bazel(conanfile)
    bazel.build(target='//test:label')
    # Uncomment Conan 2.x
    # assert 'bazel build //test:label' in conanfile.commands
    assert 'bazel build //test:label' == str(conanfile.command)


@pytest.mark.skipif(platform.system() == "Windows", reason="Remove this skip for Conan 2.x."
                                                           "Needs conanfile.commands")
def test_bazel_command_with_config_values():
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.google.bazel:configs", ["config", "config2"])
    conanfile.conf.define("tools.google.bazel:bazelrc_path", ["/path/to/bazelrc"])
    bazel = Bazel(conanfile)
    bazel.build(target='//test:label')
    # Uncomment Conan 2.x
    # assert "bazel --bazelrc=/path/to/bazelrc build " \
    #        "--config=config --config=config2 //test:label" in conanfile.commands
    assert "bazel --bazelrc=/path/to/bazelrc build " \
           "--config=config --config=config2 //test:label" == str(conanfile.command)
