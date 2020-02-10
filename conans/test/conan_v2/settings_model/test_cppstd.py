import textwrap

import six

from conans.client import settings_preprocessor
from conans.client.conf import get_default_settings_yml
from conans.errors import ConanV2Exception, ConanException
from conans.model.settings import Settings
from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


class SettingsCppstdTestCase(ConanV2ModeTestCase):
    def test_recipe_invalid(self):
        # If a recipe declares 'settings = "os", ..., "cppstd", it fails
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            
            class Recipe(ConanFile):
                settings = "os", "cppstd"
        """)
        t = self.get_client()
        t.save({'conanfile.py': conanfile})
        t.run("create . name/version@", assert_error=True)
        #self.assertIn("Conan v2 incompatible: Setting 'cppstd' is deprecated", t.out)
        self.assertIn("ERROR: Error while initializing settings. 'settings.cppstd' doesn't exist", t.out)

    def test_settings_model(self):
        # First level setting 'cppstd' is no longer supported
        settings = Settings.loads(get_default_settings_yml())

        #with six.assertRaisesRegex(self, ConanV2Exception, "Setting 'cppstd' is deprecated"):
        with six.assertRaisesRegex(self, ConanException, "'settings.cppstd' doesn't exist"):
            settings.cppstd = "11"
            settings_preprocessor.preprocess(settings=settings)
