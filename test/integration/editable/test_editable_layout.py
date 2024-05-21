import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_editable_folders_root():
    """ Editables with self.folders.root = ".." should work too
    """
    c = TestClient()
    pkg = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def layout(self):
                self.folders.root = ".."
                self.folders.build = "mybuild"
                self.cpp.build.libdirs = ["mylibdir"]

            def generate(self):
                self.output.info(f"PKG source_folder {self.source_folder}")

            def package_info(self):
                self.output.info(f"PKG package_folder {self.package_folder}")
        """)
    app = textwrap.dedent("""
        from conan import ConanFile

        class App(ConanFile):
            requires = "pkg/0.1"
            def generate(self):
                pkg_libdir = self.dependencies["pkg"].cpp_info.libdir
                self.output.info(f"PKG LIBDIR {pkg_libdir}")
        """)
    c.save({"libs/pkg/conanfile.py": pkg,
            "conanfile.py": app})

    c.run("editable add libs/pkg")
    c.run("install .")
    libdir = os.path.join(c.current_folder, "libs", "mybuild", "mylibdir")
    assert f"conanfile.py: PKG LIBDIR {libdir}" in c.out
    assert f"pkg/0.1: PKG package_folder {c.current_folder}" in c.out
    assert f"pkg/0.1: PKG source_folder {c.current_folder}" in c.out


def test_editable_folders_sibiling_root():
    """ Editables with self.folders.root = ".." should work too for sibling folders
    """
    c = TestClient()
    pkg = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def layout(self):
                self.folders.root = ".."
                self.folders.build = "mybuild"
                self.cpp.build.libdirs = ["mylibdir"]

            def generate(self):
                self.output.info(f"PKG source_folder {self.source_folder}")

            def package_info(self):
                self.output.info(f"PKG package_folder {self.package_folder}")
        """)
    app = textwrap.dedent("""
        from conan import ConanFile

        class App(ConanFile):
            requires = "pkg/0.1"
            def generate(self):
                pkg_libdir = self.dependencies["pkg"].cpp_info.libdir
                self.output.info(f"PKG LIBDIR {pkg_libdir}")
        """)
    c.save({"pkg/conanfile.py": pkg,
            "app/conanfile.py": app})

    c.run("editable add pkg")
    c.run("install app")
    libdir = os.path.join(c.current_folder, "mybuild", "mylibdir")
    assert f"conanfile.py: PKG LIBDIR {libdir}" in c.out
    assert f"pkg/0.1: PKG source_folder {c.current_folder}" in c.out
    assert f"pkg/0.1: PKG package_folder {c.current_folder}" in c.out


def test_editable_matching_folder_names():
    # https://github.com/conan-io/conan/issues/14091
    client = TestClient()
    client.save({"hello-say/conanfile.py": GenConanfile("say", "0.1"),
                 "hello/conanfile.py": GenConanfile("hello", "0.1").with_settings("build_type")
                                                                   .with_require("say/0.1")})
    client.run("editable add hello-say")
    client.run("build hello-say")
    client.run("install hello -g CMakeDeps -s:b os=Linux")
    data = client.load("hello/say-release-data.cmake")
    hello_say_folder = os.path.join(client.current_folder, "hello-say").replace("\\", "/")
    assert f'set(say_PACKAGE_FOLDER_RELEASE "{hello_say_folder}")' in data
    env = client.load("hello/conanbuildenv-release.sh")
    assert "$script_folder/deactivate_conanbuildenv-release.sh" in env.replace("\\", "/")


def test_install_editable_build_folder_vars():
    """ Make sure that the consumer generates the editable files following build_folder_vars
    """
    c = TestClient()
    profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        build_type=Release
        [conf]
        tools.cmake.cmake_layout:build_folder_vars=['settings.os', 'settings.arch']
        """)
    lib = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout
        class Lib(ConanFile):
            name = "lib"
            version = "0.1"
            settings = "os", "arch", "build_type"
            generators = "CMakeToolchain"

            def layout(self):
                cmake_layout(self)
            """)
    app = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout
        class App(ConanFile):
            settings = "os", "arch", "build_type"
            requires = "lib/0.1"
            generators = "CMakeToolchain"

            def layout(self):
                cmake_layout(self)
            """)
    c.save({"lib/conanfile.py": lib,
            "app/conanfile.py": app,
            "profile": profile})
    c.run("editable add lib")
    c.run("build lib -pr=profile")
    c.run("install app -pr=profile")
    path = os.path.join(c.current_folder, "lib", "build", "windows-x86_64", "Release", "generators")
    assert f"lib/0.1: Writing generators to {path}" in c.out
