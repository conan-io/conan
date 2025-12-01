import textwrap

import pytest

from conan.test.utils.tools import TestClient

simple = """
from conan import ConanFile
class Pkg(ConanFile):
    options = {"shared": [True, False],
               "header_only": [True, False]}
"""

pkg_type = """
from conan import ConanFile
class Pkg(ConanFile):
    package_type = "library"
    options = {"shared": [True, False],
               "header_only": [True, False]}
"""

remove = """
from conan import ConanFile
class Pkg(ConanFile):
    package_type = "library"
    options = {"shared": [True, False],
               "header_only": [True, False]}
    def configure(self):
        if self.options.header_only:
            self.options.rm_safe("shared")
"""


@pytest.mark.parametrize("conanfile", [simple, pkg_type, remove])
def test_auto_package_type(conanfile):
    c = TestClient(light=True)
    c.save({"conanfile.py": conanfile})
    c.run("graph info . --filter package_type")
    assert "package_type: static-library" in c.out
    c.run("graph info . --filter package_type -o shared=True")
    assert "The package_type will have precedence over the options" not in c.out
    assert "package_type: shared-library" in c.out
    c.run("graph info . --filter package_type -o shared=True -o header_only=False")
    assert "package_type: shared-library" in c.out
    c.run("graph info . --filter package_type -o header_only=True")
    assert "package_type: header-library" in c.out
    c.run("graph info . --filter package_type -o header_only=True -o shared=False")
    assert "package_type: header-library" in c.out

def test_package_type_and_header_library():
    """ Show that forcing a package_type and header_only=True does not change the package_type"""
    tc = TestClient(light=True)
    tc.save({"conanfile.py": textwrap.dedent("""
    from conan import ConanFile

    class Pkg(ConanFile):
        package_type = "static-library"
        options = {"header_only": [True, False]}

    """)})
    tc.run("graph info . --filter package_type -o &:header_only=False")
    assert "package_type: static-library" in tc.out
    assert "The package_type will have precedence over the options" in tc.out
    tc.run("graph info . --filter package_type -o &:header_only=True")
    assert "package_type: static-library" in tc.out
    assert "The package_type will have precedence over the options" in tc.out
