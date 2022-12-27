import os
import textwrap

from conan.tools import CONAN_TOOLCHAIN_ARGS_FILE
from conan.tools.files.files import load_toolchain_args
from conans.test.utils.tools import TestClient


def test_bazel_namespace():
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
    tools.google.bazel:configs=["test_config"]
    tools.google.bazel:bazelrc_path=/path/to/bazelrc
    """)

    client.save({"test_profile": profile})

    client.save({"conanfile.py": conanfile})
    client.run("install . -pr test_profile")
    assert os.path.isfile(os.path.join(client.current_folder,
                                       "{}_{}".format(namespace, CONAN_TOOLCHAIN_ARGS_FILE)))
    content = load_toolchain_args(generators_folder=client.current_folder, namespace=namespace)
    bazel_config = content.get("bazel_configs")
    bazelrc_path = content.get("bazelrc_path")
    client.run("build .")
    assert bazel_config in client.out
    assert bazelrc_path in client.out


def test_autotools_namespace():
    client = TestClient()
    namespace = "somename"
    conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.gnu import AutotoolsToolchain, Autotools

            class Conan(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                def generate(self):
                    autotools = AutotoolsToolchain(self, namespace='{0}')
                    autotools.configure_args = ['a', 'b']
                    autotools.make_args = ['c', 'd']
                    autotools.generate()
                def build(self):
                    autotools = Autotools(self, namespace='{0}')
                    self.output.info(autotools._configure_args)
                    self.output.info(autotools._make_args)
            """.format(namespace))

    client.save({"conanfile.py": conanfile})
    client.run("install .")
    assert os.path.isfile(os.path.join(client.current_folder,
                                       "{}_{}".format(namespace, CONAN_TOOLCHAIN_ARGS_FILE)))
    content = load_toolchain_args(generators_folder=client.current_folder, namespace=namespace)
    at_configure_args = content.get("configure_args")
    at_make_args = content.get("make_args")
    client.run("build .")
    assert at_configure_args in client.out
    assert at_make_args in client.out


def test_multiple_toolchains_one_recipe():
    # https://github.com/conan-io/conan/issues/9376
    client = TestClient()
    namespaces = ["autotools", "bazel"]
    conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.gnu import AutotoolsToolchain, Autotools
            from conan.tools.google import BazelToolchain, Bazel

            class Conan(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                def generate(self):
                    autotools = AutotoolsToolchain(self, namespace='{0}')
                    autotools.configure_args = ['a', 'b']
                    autotools.make_args = ['c', 'd']
                    autotools.generate()
                    bazel = BazelToolchain(self, namespace='{1}')
                    bazel.generate()

                def build(self):
                    autotools = Autotools(self, namespace='{0}')
                    self.output.info(autotools._configure_args)
                    self.output.info(autotools._make_args)
                    bazel = Bazel(self, namespace='{1}')
                    self.output.info(bazel._bazel_config)
                    self.output.info(bazel._bazelrc_path)
            """.format(*namespaces))

    client.save({"conanfile.py": conanfile})

    profile = textwrap.dedent("""
    include(default)
    [conf]
    tools.google.bazel:configs=["test_config"]
    tools.google.bazel:bazelrc_path=/path/to/bazelrc
    """)

    client.save({"test_profile": profile})

    client.run("install . -pr test_profile")
    check_args = {
        "autotools": ["configure_args", "make_args"],
        "bazel": ["bazel_configs", "bazelrc_path"],
    }
    checks = []
    for namespace in namespaces:
        assert os.path.isfile(os.path.join(client.current_folder,
                                           "{}_{}".format(namespace, CONAN_TOOLCHAIN_ARGS_FILE)))
        content = load_toolchain_args(generators_folder=client.current_folder, namespace=namespace)
        for arg in check_args.get(namespace):
            checks.append(content.get(arg))
    client.run("build .")
    for check in checks:
        assert check in client.out
