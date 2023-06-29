import textwrap
import unittest

from parameterized import parameterized

from conans.test.utils.tools import TestClient


class ConfigureOptionsTest(unittest.TestCase):
    """
    Test config_options() and configure() methods can manage shared, fPIC and header_only options
    automatically
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
        Test that options are managed automatically when methods config_otpions and configure are not
        defined
        """
        client = TestClient()
        conanfile = textwrap.dedent(f"""\
           from conan import ConanFile

           class Pkg(ConanFile):
               settings = "os", "compiler", "arch", "build_type"
               options = {{"shared": [True, False], "fPIC": [True, False], "header_only": [True, False]}}
               default_options = {{"shared": {shared}, "fPIC": {fpic}, "header_only": {header_only}}}

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
        Test that options are not managed automatically when methods are defined
        """
        client = TestClient()
        conanfile = textwrap.dedent(f"""\
           from conan import ConanFile

           class Pkg(ConanFile):
               settings = "os", "compiler", "arch", "build_type"
               options = {{"shared": [True, False], "fPIC": [True, False], "header_only": [True, False]}}
               default_options = {{"shared": {shared}, "fPIC": {fpic}, "header_only": {header_only}}}

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
    def test_methods_defined_explicit(self, settings_os, shared, fpic, header_only, result):
        """
        Test that options are managed automatically when methods config_otpions and configure are not
        defined
        """
        client = TestClient()
        conanfile = textwrap.dedent(f"""\
               from conan import ConanFile
               from conan.tools.options import handle_common_config_options, handle_common_configure_options

               class Pkg(ConanFile):
                   settings = "os", "compiler", "arch", "build_type"
                   options = {{"shared": [True, False], "fPIC": [True, False], "header_only": [True, False]}}
                   default_options = {{"shared": {shared}, "fPIC": {fpic}, "header_only": {header_only}}}

                   def config_options(self):
                       handle_common_config_options(self)

                   def configure(self):
                       handle_common_configure_options(self)

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
