import textwrap
import unittest

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase
from conans.test.utils.tools import TestClient
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID


class ConanfileSourceTestCase(ConanV2ModeTestCase):
    """ Conan v2: 'self.info' is not available in 'package()' """

    def test_info_not_in_package(self):
        # self.info is not available in 'package'
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
            
                def package(self):
                    self.info.header_only()
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . name/version@ -s os=Linux', assert_error=True)
        self.assertIn("Conan v2 incompatible: 'self.info' access in package() method is deprecated", t.out)


class ConanfileSourceV1TestCase(unittest.TestCase):
    """ Conan v1 will show a warning """

    def test_v1_warning(self):
        t = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
            
                def package(self):
                    self.info.header_only()  # No sense, it will warn the user
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . name/version@')
        self.assertIn("name/version: WARN: 'self.info' access in package() method is deprecated", t.out)
