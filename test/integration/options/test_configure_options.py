import textwrap
import unittest

from parameterized import parameterized

from conan.test.utils.tools import TestClient


class ConfigureOptionsTest(unittest.TestCase):
    """
    Test config_options(), configure() and package_id() methods can manage shared, fPIC and
    header_only options automatically.
    """

    @parameterized.expand([
        ["Linux", False, False, False, [False, False, False]],
        ["Windows", False, False, False, [False, None, False]],
        ["Windows", True, False, False, [True, None, False]],
        ["Windows", False, False, True, [None, None, True]],
        ["Linux", False, False, True, [None, None, True]],
        ["Linux", True, True, False, [True, None, False]],
        ["Linux", True, False, False, [True, None, False]],
        ["Linux", True, True, True, [None, None, True]],
        ["Linux", True, True, True, [None, None, True]],
        ["Linux", False, True, False, [False, True, False]],
        ["Linux", False, True, False, [False, True, False]],
    ])
    def test_methods_not_defined(self, settings_os, shared, fpic, header_only, result):
        """
        Test that options are managed automatically when methods config_options and configure are not
        defined and implements = ["auto_shared_fpic", "auto_header_only"].
        Check that header only package gets its unique package ID.
        """
        client = TestClient()
        conanfile = textwrap.dedent(f"""\
           from conan import ConanFile

           class Pkg(ConanFile):
               settings = "os", "compiler", "arch", "build_type"
               options = {{"shared": [True, False], "fPIC": [True, False], "header_only": [True, False]}}
               default_options = {{"shared": {shared}, "fPIC": {fpic}, "header_only": {header_only}}}
               implements = ["auto_shared_fpic", "auto_header_only"]

               def build(self):
                   shared = self.options.get_safe("shared")
                   fpic = self.options.get_safe("fPIC")
                   header_only = self.options.get_safe("header_only")
                   self.output.info(f"shared: {{shared}}, fPIC: {{fpic}}, header only: {{header_only}}")
            """)
        client.save({"conanfile.py": conanfile})
        client.run(f"create . --name=pkg --version=0.1 -s os={settings_os}")
        result = f"shared: {result[0]}, fPIC: {result[1]}, header only: {result[2]}"
        self.assertIn(result, client.out)
        if header_only:
            self.assertIn("Package 'da39a3ee5e6b4b0d3255bfef95601890afd80709' created", client.out)

    @parameterized.expand([
        ["Linux", False, False, False, [False, False, False]],
        ["Linux", False, False, True, [False, False, True]],
        ["Linux", False, True, False, [False, True, False]],
        ["Linux", False, True, True, [False, True, True]],
        ["Linux", True, False, False, [True, False, False]],
        ["Linux", True, False, True, [True, False, True]],
        ["Linux", True, True, False, [True, True, False]],
        ["Linux", True, True, True, [True, True, True]],
        ["Windows", False, False, False, [False, False, False]],
        ["Windows", False, False, True, [False, False, True]],
        ["Windows", False, True, False, [False, True, False]],
        ["Windows", False, True, True, [False, True, True]],
        ["Windows", True, False, False, [True, False, False]],
        ["Windows", True, False, True, [True, False, True]],
        ["Windows", True, True, False, [True, True, False]],
        ["Windows", True, True, True, [True, True, True]],
    ])
    def test_optout(self, settings_os, shared, fpic, header_only, result):
        """
        Test that options are not managed automatically when methods are defined even if implements = ["auto_shared_fpic", "auto_header_only"]
        Check that header only package gets its unique package ID.
        """
        client = TestClient()
        conanfile = textwrap.dedent(f"""\
           from conan import ConanFile

           class Pkg(ConanFile):
               settings = "os", "compiler", "arch", "build_type"
               options = {{"shared": [True, False], "fPIC": [True, False], "header_only": [True, False]}}
               default_options = {{"shared": {shared}, "fPIC": {fpic}, "header_only": {header_only}}}
               implements = ["auto_shared_fpic", "auto_header_only"]

               def config_options(self):
                   pass

               def configure(self):
                   pass

               def build(self):
                   shared = self.options.get_safe("shared")
                   fpic = self.options.get_safe("fPIC")
                   header_only = self.options.get_safe("header_only")
                   self.output.info(f"shared: {{shared}}, fPIC: {{fpic}}, header only: {{header_only}}")
            """)
        client.save({"conanfile.py": conanfile})
        client.run(f"create . --name=pkg --version=0.1 -s os={settings_os}")
        result = f"shared: {result[0]}, fPIC: {result[1]}, header only: {result[2]}"
        self.assertIn(result, client.out)
        if header_only:
            self.assertIn("Package 'da39a3ee5e6b4b0d3255bfef95601890afd80709' created", client.out)

    def test_header_package_type_pid(self):
        """
        Test that we get the pid for header only when package type is set to header-library
        """
        client = TestClient()
        conanfile = textwrap.dedent(f"""\
               from conan import ConanFile

               class Pkg(ConanFile):
                   settings = "os", "compiler", "arch", "build_type"
                   package_type = "header-library"
                   implements = ["auto_shared_fpic", "auto_header_only"]

                """)
        client.save({"conanfile.py": conanfile})
        client.run(f"create . --name=pkg --version=0.1")
        self.assertIn("Package 'da39a3ee5e6b4b0d3255bfef95601890afd80709' created", client.out)


def test_possible_values_based_on_version():
    tc = TestClient(light=True)
    tc.save({"conanfile.py": textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.scm import Version

    class Pkg(ConanFile):
        name = "foo"
        options = {"my_option": ["foo", "v1", "v2"]}
        default_options = {"my_option": "foo"}
        def config_options(self):
            if Version(self.version) < "2.0":
                self.options.constrain_possible_values("my_option", ["foo", "v1"])
            else:
                self.options.constrain_possible_values("my_option", ["foo", "v2"])

    """)})

    tc.run("graph info . --version=1.0 -o='&:my_option=v1'")
    tc.run("graph info . --version=1.0 -o='&:my_option=v2'", assert_error=True)
    assert "ERROR: 'v2' is not a valid 'options.my_option' value.\nPossible values are ['foo', 'v1']" in tc.out
    tc.run("graph info . --version=1.0 -o='&:my_option=foo'")

    tc.run("graph info . --version=2.0 -o='&:my_option=v1'", assert_error=True)
    assert "ERROR: 'v1' is not a valid 'options.my_option' value.\nPossible values are ['foo', 'v2']" in tc.out
    tc.run("graph info . --version=2.0 -o='&:my_option=v2'")
    tc.run("graph info . --version=2.0 -o='&:my_option=foo'")


def test_possible_values_based_on_version_when_frozen():
    tc = TestClient(light=True)
    tc.save({"conanfile.py": textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.scm import Version

    class Pkg(ConanFile):
        name = "foo"
        options = {"my_option": ["foo", "v1", "v2"]}
        default_options = {"my_option": "foo"}
        def configure(self):
            if Version(self.version) < "2.0":
                self.options.constrain_possible_values("my_option", ["foo", "v1"])
            else:
                self.options.constrain_possible_values("my_option", ["foo", "v2"])

    """)})

    tc.run("graph info . --version=2.0 -o='&:my_option=v1'", assert_error=True)
    assert "Cannot constrain option 'my_option' possible values after it has been set to 'v1'" in tc.out


def test_possible_values_unknown_option():
    tc = TestClient(light=True)
    tc.save({"conanfile.py": textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.scm import Version

    class Pkg(ConanFile):
        name = "foo"
        options = {"my_option": ["foo", "v1", "v2"]}
        default_options = {"my_option": "foo"}
        def configure(self):
            self.options.constrain_possible_values("bad_option", ["foo", "v1"])

    """)})

    tc.run("graph info . --version=2.0", assert_error=True)
    assert "ConanException: option 'bad_option' doesn't exist" in tc.out
