import textwrap

from conans.test.utils.conan_v2_tests import ConanV2ModeTestCase


# TODO: These tests related to 'settings' need to work using ``default_config_yml -- CONAN_V2`` (without
#   some settings like `os_build`, `arch_build`, `ccpstd`,...) but they have to fail also if the user
#   has a modified settings.yml.

class SettingsBuildTestCase(ConanV2ModeTestCase):
    def test_os_build_deprecated(self):
        # If a recipe declares 'settings = "os_build" it fails
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                settings = "os_build"
        """)
        t = self.get_client()
        t.save({'conanfile.py': conanfile})
        t.run("create . name/version@", assert_error=True)
        #self.assertIn("Conan v2 incompatible: Setting 'os_build' is deprecated", t.out)
        self.assertIn("ERROR: Error while initializing settings. 'settings.os_build' doesn't exist", t.out)

    def test_arch_build_deprecated(self):
        # If a recipe declares 'settings = "arch_build" it fails
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                settings = "arch_build"
        """)
        t = self.get_client()
        t.save({'conanfile.py': conanfile})
        t.run("create . name/version@", assert_error=True)
        #self.assertIn("Conan v2 incompatible: Setting 'arch_build' is deprecated", t.out)
        self.assertIn("ERROR: Error while initializing settings. 'settings.arch_build' doesn't exist", t.out)


class SettingsTargetTestCase(ConanV2ModeTestCase):
    def test_os_target_deprecated(self):
        # If a recipe declares 'settings = "os_target" it fails
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                settings = "os_target"
        """)
        t = self.get_client()
        t.save({'conanfile.py': conanfile})
        t.run("create . name/version@", assert_error=True)
        #self.assertIn("Conan v2 incompatible: Setting 'os_target' is deprecated", t.out)
        self.assertIn("ERROR: Error while initializing settings. 'settings.os_target' doesn't exist", t.out)

    def test_arch_target_deprecated(self):
        # If a recipe declares 'settings = "arch_target" it fails
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                settings = "arch_target"
        """)
        t = self.get_client()
        t.save({'conanfile.py': conanfile})
        t.run("create . name/version@", assert_error=True)
        #self.assertIn("Conan v2 incompatible: Setting 'arch_target' is deprecated", t.out)
        self.assertIn("ERROR: Error while initializing settings. 'settings.arch_target' doesn't exist", t.out)

