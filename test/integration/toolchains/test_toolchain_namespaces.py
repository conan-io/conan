import os
import textwrap

from conan.tools.build import load_toolchain_args, CONAN_TOOLCHAIN_ARGS_FILE
from conan.test.utils.tools import TestClient


def test_autotools_namespace():
    client = TestClient()
    namespace = "somename"
    conanfile = textwrap.dedent("""
            from conan import ConanFile
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
