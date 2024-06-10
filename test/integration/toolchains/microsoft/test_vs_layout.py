import os
import textwrap

from conan.test.utils.tools import TestClient


def test_vs_layout_subproject():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.microsoft import vs_layout
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "MSBuildToolchain"
            def layout(self):
                self.folders.root = ".."
                self.folders.subproject = "pkg"
                vs_layout(self)
        """)
    c.save({"pkg/conanfile.py": conanfile})
    c.run("install pkg")
    assert os.path.isfile(os.path.join(c.current_folder, "pkg", "conan", "conantoolchain.props"))
