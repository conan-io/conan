import os
import textwrap

from conan.tools import CONAN_TOOLCHAIN_ARGS_FILE
from conan.tools.files import load_toolchain_args
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
    tools.google.bazel:config=test_config
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
    assert config['bazel_config'] == "test_config"
    assert config['bazelrc_path'] == "/path/to/bazelrc"


def test_namespace():
    client = TestClient()
    namespace = "somename"
    conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.google import BazelToolchain, Bazel

            class Conan(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                def generate(self):
                    bazel = BazelToolchain(self, namespace='{0}')
                    bazel.generate()
                def build(self):
                    bazel = Bazel(self, namespace='{0}')
                    self.output.info(bazel._bazel_config)
                    self.output.info(bazel._bazelrc_path)
            """.format(namespace))

    profile = textwrap.dedent("""
    include(default)
    [conf]
    tools.google.bazel:config=test_config
    tools.google.bazel:bazelrc_path=/path/to/bazelrc
    """)

    client.save({"test_profile": profile})

    client.save({"conanfile.py": conanfile})
    client.run("install . -pr test_profile")
    assert os.path.isfile(os.path.join(client.current_folder,
                                       "{}_{}".format(namespace, CONAN_TOOLCHAIN_ARGS_FILE)))
    content = load_toolchain_args(generators_folder=client.current_folder, namespace=namespace)
    bazel_config = content.get("bazel_config")
    bazelrc_path = content.get("bazelrc_path")
    client.run("build .")
    assert bazel_config in client.out
    assert bazelrc_path in client.out
