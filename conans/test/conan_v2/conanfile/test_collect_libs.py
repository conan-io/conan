import textwrap

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class CollectLibsTestCase(ConanV2ModeTestCase):

    def test_self_collect_libs(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                def package_info(self):
                    libs = self.collect_libs()
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . name/version@', assert_error=True)
        self.assertIn("Conan v2 incompatible: 'self.collect_libs' is deprecated", t.out)
