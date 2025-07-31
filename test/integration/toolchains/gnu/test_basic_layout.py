import os
import platform
import textwrap
import pytest

from conan.test.utils.tools import TestClient

@pytest.mark.parametrize("basic_layout, expected_path", [
    ('basic_layout(self)', 'build-release'),
    ('basic_layout(self, build_folder="custom_build_folder")', 'custom_build_folder')])
def test_basic_layout_subproject(basic_layout, expected_path):
    c = TestClient()
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.layout import basic_layout
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "AutotoolsToolchain"
            def layout(self):
                self.folders.root = ".."
                self.folders.subproject = "pkg"
                {basic_layout}
        """)
    c.save({"pkg/conanfile.py": conanfile})
    c.run("install pkg")
    ext = "sh" if platform.system() != "Windows" else "bat"
    assert os.path.isfile(os.path.join(c.current_folder, "pkg", expected_path, "conan",
                                       "conanautotoolstoolchain.{}".format(ext)))
