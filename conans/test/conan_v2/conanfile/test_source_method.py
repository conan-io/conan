import textwrap
import unittest

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase
from conans.test.utils.tools import TestClient


class ConanfileSourceTestCase(ConanV2ModeTestCase):
    """ Conan v2: Settings and options are not available in method 'source()' """

    def test_proper_usage(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, tools

            class Recipe(ConanFile):
                settings = "os",
                options = {'shared': [True, False]}

                def source(self):
                    self.output.info("conanfile::source()")
                
                def build(self):
                    self.output.info("conanfile::build(): settings.os={}".format(self.settings.os))
                    self.output.info("conanfile::build(): options.shared={}".format(self.options.shared))
                
                def package(self):
                    tools.save(os.path.join(self.package_folder, 'file'), "AAA")  # Avoid package() WARN
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . name/version@ -o shared=False -s os=Linux')
        self.assertIn("name/version: conanfile::source()", t.out)
        self.assertIn("name/version: conanfile::build(): settings.os=Linux", t.out)
        self.assertIn("name/version: conanfile::build(): options.shared=False", t.out)
        self.assertNotIn("WARN", t.out)

    def test_no_settings(self):
        # self.setting is not available in 'source'
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                settings = "os",

                def source(self):
                    self.output.info("conanfile::source(): settings.os={}".format(self.settings.os))
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . name/version@ -s os=Linux', assert_error=True)
        self.assertIn("Conan v2 incompatible: 'self.settings' access in source() method is deprecated", t.out)

    def test_no_options(self):
        # self.setting is not available in 'source'
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                options = {'shared': [True, False]}

                def source(self):
                    self.output.info("conanfile::source(): options.shared={}".format(self.options.shared))
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . name/version@ -o shared=False', assert_error=True)
        self.assertIn("Conan v2 incompatible: 'self.options' access in source() method is deprecated", t.out)


class ConanfileSourceV1TestCase(unittest.TestCase):
    """ Conan v1 will show a warning """

    def test_v1_warning(self):
        t = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                settings = "os",
                options = {'shared': [True, False]}

                def source(self):
                    self.output.info("conanfile::source(): settings.os={}".format(self.settings.os))
                    self.output.info("conanfile::source(): options.shared={}".format(self.options.shared))
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . name/version@ -o shared=False -s os=Linux')
        self.assertIn("name/version: WARN: 'self.settings' access in source() method is deprecated", t.out)
        self.assertIn("name/version: WARN: 'self.options' access in source() method is deprecated", t.out)
        self.assertIn("name/version: conanfile::source(): settings.os=Linux", t.out)
        self.assertIn("name/version: conanfile::source(): options.shared=False", t.out)
