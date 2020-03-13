import textwrap

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class DefaultOptionsSyntaxTestCase(ConanV2ModeTestCase):
    msg = "Conan v2 incompatible: Declare 'default_options' as a dictionary"

    def test_deprecate_string(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                options = {"option": [True, False]}
                default_options = "option=True"
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . name/version@', assert_error=True)
        self.assertIn(self.msg, t.out)

        t.run('inspect . -a default_options', assert_error=True)
        self.assertIn(self.msg, t.out)

    def test_deprecate_list(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                options = {"option": [True, False], "option2": [False, ]}
                default_options = "option=True", "option2=False"
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . name/version@', assert_error=True)
        self.assertIn(self.msg, t.out)

        t.run('inspect . -a default_options', assert_error=True)
        self.assertIn(self.msg, t.out)

    def test_deprecate_tuple(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                options = {"option": [True, False], "option2": [False, ]}
                default_options = ("option=True", "option2=False", )
        """)
        t.save({'conanfile.py': conanfile})
        t.run('create . name/version@', assert_error=True)
        self.assertIn(self.msg, t.out)

        t.run('inspect . -a default_options', assert_error=True)
        self.assertIn(self.msg, t.out)
