import os
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_editable_folders_root():
    """ Editables with self.folders.root = ".." should work too
    """
    c = TestClient()
    sub1 = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            def layout(self):
                self.folders.root = ".."
                self.folders.build = "mybuild"
                self.cpp.build.libdirs = ["mylibdir"]
        """)
    sub2 = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            requires = "pkg/0.1"
            def generate(self):
                pkg_libdir = self.dependencies["pkg"].cpp_info.libdir
                self.output.info(f"PKG LIBDIR {pkg_libdir}")
        """)
    c.save({"sub1/conanfile.py": sub1,
            "sub2/conanfile.py": sub2})
    c.run("editable add sub1")
    c.run("install sub2")
    libdir = os.path.join(c.current_folder, "mybuild", "mylibdir")
    assert f"conanfile.py: PKG LIBDIR {libdir}" in c.out


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
