import textwrap

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class ConfigMethodTestCase(ConanV2ModeTestCase):

    def test_config_method(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                def config(self):
                    pass
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . name/version@', assert_error=True)
        self.assertIn("Conan v2 incompatible: config() has been deprecated. Use config_options() and configure()",
                      t.out)
