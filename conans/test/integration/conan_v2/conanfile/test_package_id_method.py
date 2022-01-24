import platform
import textwrap
import unittest

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase
from conans.test.utils.tools import TestClient


class ConanfileSourceTestCase(ConanV2ModeTestCase):
    """ Conan v2: 'self.cpp_info' is not available in 'package_id()' """

    def test_cppinfo_not_in_package_id(self):
        # self.cpp_info is not available in 'package_id'
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):

                def package_id(self):
                    self.cpp_info.libs = ["A"]
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . --name=name --version=version -s os=Linux', assert_error=True)
        self.assertIn("'self.cpp_info' access in package_id() method is deprecated", t.out)

