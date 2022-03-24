import textwrap

from conan.tools.files.files import load_toolchain_args
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_toolchain_empty_config():
    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "compiler", "build_type", "arch").\
        with_generator("BazelToolchain")

    client.save({"conanfile.py": conanfile})
    client.run("install .")

    config = load_toolchain_args(client.current_folder)
    assert not config


def test_toolchain_loads_config_from_profile():
    client = TestClient(path_with_spaces=False)

    profile = textwrap.dedent("""
    include(default)
    [conf]
    tools.google.bazel:configs=["test_config", "test_config2"]
    tools.google.bazel:bazelrc_path=/path/to/bazelrc
    """)

    conanfile = GenConanfile().with_settings("os", "compiler", "build_type", "arch").\
        with_generator("BazelToolchain")

    client.save({
        "conanfile.py": conanfile,
        "test_profile": profile
    })
    client.run("install . -pr=test_profile")

    config = load_toolchain_args(client.current_folder)
    assert config['bazel_configs'] == "test_config,test_config2"
    assert config['bazelrc_path'] == "/path/to/bazelrc"
