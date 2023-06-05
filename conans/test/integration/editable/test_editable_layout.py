import os
import textwrap

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
