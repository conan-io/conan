import os
import platform
import textwrap

from conans.test.utils.tools import TestClient


def test_basic_layout_subproject():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.layout import basic_layout
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "AutotoolsToolchain"
            def layout(self):
                self.folders.root = ".."
                self.folders.subproject = "pkg"
                basic_layout(self)
        """)
    c.save({"pkg/conanfile.py": conanfile})
    c.run("install pkg")
    ext = "sh" if platform.system() != "Windows" else "bat"
    assert os.path.isfile(os.path.join(c.current_folder, "pkg", "build-release", "conan",
                                       "conanautotoolstoolchain.{}".format(ext)))


# TODO: Remove this test in 2.0
def test_basic_layout_no_generators():
    """ test that conan doesn't crash for auto_use=True
    because generator folder doesn't exist
    # https://github.com/conan-io/conan/issues/12383
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.layout import basic_layout
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"
            def layout(self):
                basic_layout(self)
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create . -c tools.env.virtualenv:auto_use=True")
    # It used to fail, if it doesn't crash, it is good
