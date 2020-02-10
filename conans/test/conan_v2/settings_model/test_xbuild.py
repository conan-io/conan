import textwrap
import unittest

from parameterized import parameterized

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


# TODO: These tests related to 'settings' need to work using ``default_config_yml -- CONAN_V2`` (without
#   some settings like `os_build`, `arch_build`, `ccpstd`,...) but they have to fail also if the user
#   has a modified settings.yml.


@unittest.skip("Wait for xbuilding PR to be merged")
class SettingsBuildTestCase(ConanV2ModeTestCase):
    @parameterized.expand([(True,), (False,)])
    def test_os_build_deprecated(self, use_settings_v1):
        # If a recipe declares 'settings = "os_build" it fails
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                settings = "os_build"
        """)
        t = self.get_client(use_settings_v1=use_settings_v1)
        t.save({'conanfile.py': conanfile})
        t.run("create . name/version@", assert_error=True)
        if use_settings_v1:
            self.assertIn("Conan v2 incompatible: Setting 'os_build' is deprecated", t.out)
        else:
            self.assertIn("ERROR: Error while initializing settings. 'settings.os_build' doesn't exist", t.out)

    @parameterized.expand([(True,), (False,)])
    def test_arch_build_deprecated(self, use_settings_v1):
        # If a recipe declares 'settings = "arch_build" it fails
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                settings = "arch_build"
        """)
        t = self.get_client(use_settings_v1=use_settings_v1)
        t.save({'conanfile.py': conanfile})
        t.run("create . name/version@ -s arch_build=x86", assert_error=True)
        if use_settings_v1:
            self.assertIn("Conan v2 incompatible: Setting 'arch_build' is deprecated", t.out)
        else:
            self.assertIn("ERROR: Error while initializing settings. 'settings.arch_build' doesn't exist", t.out)


@unittest.skip("Wait for xbuilding PR to be merged")
class SettingsTargetTestCase(ConanV2ModeTestCase):
    @parameterized.expand([(True,), (False,)])
    def test_os_target_deprecated(self, use_settings_v1):
        # If a recipe declares 'settings = "os_target" it fails
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                settings = "os_target"
        """)
        t = self.get_client(use_settings_v1=use_settings_v1)
        t.save({'conanfile.py': conanfile})
        t.run("create . name/version@", assert_error=True)
        if use_settings_v1:
            self.assertIn("Conan v2 incompatible: Setting 'os_target' is deprecated", t.out)
        else:
            self.assertIn("ERROR: Error while initializing settings. 'settings.os_target' doesn't exist", t.out)

    @parameterized.expand([(True,), (False,)])
    def test_arch_target_deprecated(self, use_settings_v1):
        # If a recipe declares 'settings = "arch_target" it fails
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                settings = "arch_target"
        """)
        t = self.get_client(use_settings_v1=use_settings_v1)
        t.save({'conanfile.py': conanfile})
        t.run("create . name/version@", assert_error=True)
        if use_settings_v1:
            self.assertIn("Conan v2 incompatible: Setting 'arch_target' is deprecated", t.out)
        else:
            self.assertIn("ERROR: Error while initializing settings. 'settings.arch_target' doesn't exist", t.out)
