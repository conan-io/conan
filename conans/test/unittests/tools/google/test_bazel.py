from conan.tools.google import Bazel
from conans.test.utils.mocks import ConanFileMock


def test_bazel_command_with_empty_config():
    conanfile = ConanFileMock()
    bazel = Bazel(conanfile)
    bazel.build(target='//test:label')
    assert 'bazel build //test:label' in conanfile.commands


def test_bazel_command_with_config_values():
    conanfile = ConanFileMock()
    conanfile.conf.define("tools.google.bazel:configs", ["config", "config2"])
    conanfile.conf.define("tools.google.bazel:bazelrc_path", ["/path/to/bazelrc"])
    bazel = Bazel(conanfile)
    bazel.build(target='//test:label')
    assert "bazel --bazelrc='/path/to/bazelrc' build " \
           "--config=config --config=config2 //test:label" in conanfile.commands
