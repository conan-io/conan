import os
import textwrap

from conans.test.utils.tools import TestClient


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
        """)
    app = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
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
    assert f"pkg/0.1: PKG source_folder {c.current_folder}" in c.out
