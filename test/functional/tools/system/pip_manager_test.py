import os
import platform
import textwrap

from conan.test.utils.tools import TestClient


def test_pip_manager():
    conanfile_meson = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system.pip_manager import pip_tool_requires
        from conan.tools.files import copy
        from conan.tools.layout import basic_layout
        import platform
        import os


        class MesonPackage(ConanFile):
            name = "pip_meson_test"
            version = "0.1"

            def layout(self):
                basic_layout(self)

            def generate(self):
                self._venv_dir = pip_tool_requires(self, "meson==1.7.1", output_forlder=self.package_folder)

            def build(self):
                self.run("meson --version")

            def finalize(self):
                copy(self, "*", src=self.immutable_package_folder, dst=self.package_folder)

            def package_info(self):
                self.cpp_info.includedirs = []
                self.cpp_info.libdirs = []
                meson_root = os.path.join(self.package_folder, "pip_venv_meson", "Scripts" if platform.system() == "Windows" else "bin")
                self.buildenv_info.prepend_path("PATH", meson_root)
                self.runenv_info.prepend_path("PATH", meson_root)
        """)

    conanfile = textwrap.dedent("""
        from conan import ConanFile


        class Recipe(ConanFile):
            name = "pip_test"
            version = "0.1"

            def requirements(self):
                self.requires("pip_meson_test/0.1")

            def build(self):
                self.run("meson --version")
        """)

    client = TestClient()
    client.save({"pip_meson/conanfile.py": conanfile_meson, "consumer/conanfile.py": conanfile})

    client.run("create pip_meson/conanfile.py --version=0.1 -c tools.system.package_manager:mode=install")

    assert "RUN: meson --version" in client.out
    assert "1.7.1" in client.out

    client.run("build consumer/conanfile.py")

    assert "RUN: meson --version" in client.out
    assert "1.7.1" in client.out
