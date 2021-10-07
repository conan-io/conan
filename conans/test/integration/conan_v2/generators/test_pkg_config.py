import textwrap

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class PkgConfigGeneratorTestCase(ConanV2ModeTestCase):

    def test_name_mismatch(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                name = "mypkg"

                def package_info(self):
                    self.cpp_info.name = "MyPkg"
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . mypkg/version@')
        t.run('install mypkg/version@ -g pkg_config', assert_error=True)

        self.assertIn("ERROR: Conan v2 incompatible: Generated file and name for pkg_config"
                      " generator will change in Conan v2 to 'MyPkg'. Use"
                      " 'self.cpp_info.names[\"pkg_config\"] = \"mypkg\"' in your recipe to"
                      " continue using current name.", t.out)

    def test_name_match(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                name = "mypkg"

                def package_info(self):
                    pass
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . mypkg/version@')
        t.run('install mypkg/version@ -g pkg_config')
        self.assertIn("Generator pkg_config created mypkg.pc", t.out)
        self.assertNotIn("Conan v2 incompatible", t.out)

    def test_names_override(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                name = "mypkg"

                def package_info(self):
                    self.cpp_info.names["pkg_config"] = "MyPkg"
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . mypkg/version@')
        t.run('install mypkg/version@ -g pkg_config')
        self.assertIn("Generator pkg_config created MyPkg.pc", t.out)
        self.assertNotIn("Conan v2 incompatible", t.out)
