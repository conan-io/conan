import textwrap

from conans.client.tools.env import _environment_add
from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class CollectLibsTestCase(ConanV2ModeTestCase):

    def test_conan_username(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                name = "name"
                version = "version"
        """)
        t.save({'conanfile.py': conanfile})

        with _environment_add({'CONAN_USERNAME': "user"}):
            t.run('create .', assert_error=True)
            self.assertIn("Conan v2 incompatible: Environment variable 'CONAN_USERNAME' is deprecated", t.out)

    def test_conan_channel(self):
        t = self.get_client()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                name = "name"
                version = "version"
                default_user = "user"
        """)
        t.save({'conanfile.py': conanfile})

        with _environment_add({'CONAN_CHANNEL': "user"}):
            t.run('create .', assert_error=True)
            self.assertIn("Conan v2 incompatible: Environment variable 'CONAN_CHANNEL' is deprecated", t.out)
