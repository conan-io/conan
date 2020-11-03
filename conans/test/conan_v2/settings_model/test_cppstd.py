import textwrap

import six
from parameterized import parameterized

from conans.client import settings_preprocessor
from conans.client.conf import get_default_settings_yml
from conans.errors import ConanV2Exception, ConanException
from conans.model.settings import Settings
from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class SettingsCppstdTestCase(ConanV2ModeTestCase):
    """ First level setting 'cppstd' is deprecated, Conan will no longer add it to the default settings
        and will fail if used in any recipe or command line
    """

    @parameterized.expand([(True,), (False,)])
    def test_recipe_invalid(self, use_settings_v1):
        # If a recipe declares 'settings = "os", ..., "cppstd", it fails
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            
            class Recipe(ConanFile):
                settings = "os", "cppstd"
        """)
        t = self.get_client(use_settings_v1=use_settings_v1)
        t.save({'conanfile.py': conanfile})
        t.run("create . name/version@", assert_error=True)
        if use_settings_v1:
            self.assertIn("Conan v2 incompatible: Setting 'cppstd' is deprecated", t.out)
        else:
            self.assertIn("ERROR: The recipe is contraining settings. 'settings.cppstd' doesn't exist", t.out)

    @parameterized.expand([(True,), (False,)])
    def test_settings_model(self, use_settings_v1):
        # First level setting 'cppstd' is no longer supported
        settings = Settings.loads(get_default_settings_yml(force_v1=use_settings_v1))
        if use_settings_v1:
            settings.cppstd = "11"
            with six.assertRaisesRegex(self, ConanV2Exception, "Setting 'cppstd' is deprecated"):
                settings_preprocessor.preprocess(settings=settings)
        else:
            with six.assertRaisesRegex(self, ConanException, "'settings.cppstd' doesn't exist"):
                settings.cppstd = "11"
                settings_preprocessor.preprocess(settings=settings)

    @parameterized.expand([(True,), (False,)])
    def test_search(self, use_settings_v1):
        # First level setting 'cppstd' is no longer supported
        t = self.get_client(use_settings_v1=use_settings_v1)
        t.run("info name/version@ -s cppstd=14", assert_error=True)
        if use_settings_v1:
            self.assertIn("Conan v2 incompatible: Setting 'cppstd' is deprecated", t.out)
        else:
            self.assertIn("ERROR: 'settings.cppstd' doesn't exist", t.out)
