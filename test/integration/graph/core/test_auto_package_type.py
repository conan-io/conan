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


@pytest.mark.parametrize("package_type, shared_value", [
    ("shared-library", False),
    ("static-library", True),
])
def test_package_type_shared_option_contradiction(package_type, shared_value):
    """
    Test that contradictory package_type and shared option raises an error.
    """
    tc = TestClient(light=True)
    tc.save({"conanfile.py": textwrap.dedent(f"""
    from conan import ConanFile

    class Pkg(ConanFile):
        package_type = "{package_type}"
        options = {{"shared": [True, False]}}
        default_options = {{"shared": {shared_value}}}

    """)})
    tc.run("graph info .", assert_error=True)
    assert f"'{package_type}' should not have 'shared' option set to {shared_value}. " \
           "Consider removing the 'shared' option" in tc.out


@pytest.mark.parametrize("package_type, shared_value", [
    ("shared-library", True),
    ("static-library", False),
])
def test_package_type_shared_option_warning(package_type, shared_value):
    """
    Test that package_type with non-contradictory shared option emits warning.
    The package_type takes precedence over the option value.
    """
    tc = TestClient(light=True)
    tc.save({"conanfile.py": textwrap.dedent(f"""
    from conan import ConanFile

    class Pkg(ConanFile):
        package_type = "{package_type}"
        options = {{"shared": [True, False]}}
        default_options = {{"shared": {shared_value}}}

    """)})
    tc.run("graph info . --filter package_type")
    assert f"package_type: {package_type}" in tc.out and \
           "The package_type will have precedence over the options" in tc.out

@pytest.mark.parametrize("package_type, shared_value", [
    ("shared-library", False),
    ("static-library", True),
])
def test_package_type_shared_option_unique_possible_option(package_type, shared_value):
    """
    Test that contradictory package_type and shared option raises an error.
    """
    tc = TestClient(light=True)
    tc.save({"conanfile.py": textwrap.dedent(f"""
    from conan import ConanFile

    class Pkg(ConanFile):
        package_type = "{package_type}"
        options = {{"shared": [{shared_value}]}}
        default_options = {{"shared": {shared_value}}}

    """)})
    tc.run("graph info", assert_error=True)
    assert f"'{package_type}' should not have 'shared' option set to {shared_value}. " \
           "Consider removing the 'shared' option" in tc.out

@pytest.mark.parametrize("package_type", [("shared-library"), ("static-library")])
def test_package_type_header_only(package_type):
    """
    Test that no error is raised when only header_only option is defined
    """
    tc = TestClient(light=True)
    tc.save({"conanfile.py": textwrap.dedent(f"""
    from conan import ConanFile

    class Pkg(ConanFile):
        package_type = "{package_type}"
        options = {{"header_only": [True, False]}}
        default_options = {{"header_only": False}}

    """)})
    tc.run("graph info")
