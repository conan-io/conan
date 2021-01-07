import textwrap

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class CppinfoCppflagsTestCase(ConanV2ModeTestCase):

    def test_deprecate_cppflags(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                def package_info(self):
                    self.cpp_info.cppflags = "aa" 
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . name/version@', assert_error=True)
        self.assertIn("Conan v2 incompatible: 'cpp_info.cppflags' is deprecated, use 'cxxflags' instead", t.out)
