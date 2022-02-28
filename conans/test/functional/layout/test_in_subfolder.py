import textwrap

from conans.test.utils.tools import TestClient


def test_exports_sources_own_code_in_subfolder():
    """ test that we can put the conanfile in a subfolder, and it can work. The key is
    the exports_sources() method that can do:
        os.path.join(self.recipe_folder, "..")
    And the layout: self.folders.root = ".."
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import load, copy
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def layout(self):
                self.folders.root = ".."
                self.folders.source = "."
                self.folders.build = "build"

            def export_sources(self):
                source_folder = os.path.join(self.recipe_folder, "..")
                copy(self, "*.txt", source_folder, self.export_sources_folder)

            def source(self):
                cmake = load(self, "CMakeLists.txt")
                self.output.info("MYCMAKE-SRC: {}".format(cmake))

            def build(self):
                path = os.path.join(self.source_folder, "CMakeLists.txt")
                cmake = load(self, path)
                self.output.info("MYCMAKE-BUILD: {}".format(cmake))
            """)
    c.save({"conan/conanfile.py": conanfile,
            "CMakeLists.txt": "mycmake!"})
    c.run("create conan")
    assert "pkg/0.1: MYCMAKE-SRC: mycmake!" in c.out
    assert "pkg/0.1: MYCMAKE-BUILD: mycmake!" in c.out

    # Local flow
    c.run("install conan")
    # SOURCE NOT CALLED! It doesnt make sense (will fail due to local exports)
    c.run("build conan")
    assert "conanfile.py (pkg/0.1): MYCMAKE-BUILD: mycmake!" in c.out
