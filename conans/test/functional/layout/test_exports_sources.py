import textwrap

from conans.test.utils.tools import TestClient


def test_exports_sources_patch():
    """
    tests that using ``self.export_sources_folder`` we can access both from the source() and build()
    methods the folder where the exported sources (patches, new build files) are. And maintain
    a local flow without exports copies
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os, shutil
        from conan import ConanFile
        from conan.tools.files import load, copy, save
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            exports_sources = "CMakeLists.txt", "patches*"

            def layout(self):
                self.folders.source = "src"

            def source(self):
                save(self, "CMakeLists.txt", "old, bad") # EMULATE A DOWNLOAD!
                base_source = self.export_sources_folder
                mypatch = load(self, os.path.join(base_source, "patches/mypatch"))
                self.output.info("MYPATCH-SOURCE {}".format(mypatch))
                shutil.copy(os.path.join(base_source, "CMakeLists.txt"),
                            "CMakeLists.txt")

            def build(self):
                path = os.path.join(self.source_folder, "CMakeLists.txt")
                cmake = load(self, path)
                self.output.info("MYCMAKE-BUILD: {}".format(cmake))
                path = os.path.join(self.export_sources_folder, "patches/mypatch")
                cmake = load(self, path)
                self.output.info("MYPATCH-BUILD: {}".format(cmake))
            """)
    c.save({"conanfile.py": conanfile,
            "patches/mypatch": "mypatch!",
            "CMakeLists.txt": "mycmake!"})
    c.run("create .")
    assert "pkg/0.1: MYPATCH-SOURCE mypatch!" in c.out
    assert "pkg/0.1: MYCMAKE-BUILD: mycmake!" in c.out
    assert "pkg/0.1: MYPATCH-BUILD: mypatch!" in c.out

    # Local flow
    c.run("install .")
    c.run("source .")
    assert "conanfile.py (pkg/0.1): MYPATCH-SOURCE mypatch!" in c.out
    assert c.load("CMakeLists.txt") == "mycmake!"  # My original one
    assert c.load("src/CMakeLists.txt") == "mycmake!"  # The one patched by "source()"
    c.run("build .")
    assert "conanfile.py (pkg/0.1): MYCMAKE-BUILD: mycmake!" in c.out
    assert "conanfile.py (pkg/0.1): MYPATCH-BUILD: mypatch!" in c.out
