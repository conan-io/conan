import textwrap

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class ConanfileSourceTestCase(ConanV2ModeTestCase):
    """ Conan v2: 'self.info' is not available in 'package()' """

    def test_info_not_in_package(self):
        # self.info is not available in 'package'
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Recipe(ConanFile):

                def package(self):
                    self.info.header_only()
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . --name=name --version=version -s os=Linux', assert_error=True)
        self.assertIn("'self.info' access in package() method is deprecated", t.out)
