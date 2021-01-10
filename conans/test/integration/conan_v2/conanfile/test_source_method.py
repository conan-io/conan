import textwrap

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class ConanfileSourceTestCase(ConanV2ModeTestCase):
    """ Conan v2: Settings and options are not available in method 'source()' """

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
