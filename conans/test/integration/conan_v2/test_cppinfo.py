import textwrap

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class CppinfoTestCase(ConanV2ModeTestCase):

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

    def test_deprecate_build_modules_as_list_extend(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                def package_info(self):
                    self.cpp_info.build_modules.extend(["aa", "bb"])
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . name/version@', assert_error=True)
        self.assertIn("Conan v2 incompatible: Use 'self.cpp_info.build_modules["
                      "\"<generator>\"].extend(['aa', 'bb'])' instead", t.out)

    def test_deprecate_build_modules_as_list_append(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                def package_info(self):
                    self.cpp_info.build_modules.append("aa")
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . name/version@', assert_error=True)
        self.assertIn("Conan v2 incompatible: Use 'self.cpp_info.build_modules["
                      "\"<generator>\"].append(\"aa\")' instead", t.out)

    def test_deprecate_build_modules_as_list(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                def package_info(self):
                    self.cpp_info.build_modules = ["aa", "bb"]
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . name/version@', assert_error=True)
        self.assertIn("Conan v2 incompatible: Use 'self.cpp_info.build_modules["
                      "\"<generator>\"] = ['aa', 'bb']' instead", t.out)
