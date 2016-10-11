import unittest
from conans.model.profile import Profile


class ProfileTest(unittest.TestCase):

    def profile_test(self):

        # Empty profile
        profile = Profile()
        dump = profile.dumps()
        new_profile = Profile.loads(dump)
        self.assertEquals(new_profile.settings, profile.settings)

        # Settings
        profile = Profile()
        profile.settings["arch"] = "x86_64"
        profile.settings["compiler.version"] = "12"
        profile.settings["compiler"] = "Visual Studio"

        dump = profile.dumps()
        new_profile = Profile.loads(dump)
        self.assertEquals(new_profile.settings, profile.settings)
        self.assertEquals(new_profile.settings["arch"], "x86_64")
        self.assertEquals(new_profile.settings["compiler.version"], "12")
        self.assertEquals(new_profile.settings["compiler"], "Visual Studio")

    def profile_dump_order_test(self):
        # Settings
        profile = Profile()
        profile.settings["compiler.version"] = "12"
        profile.settings["arch"] = "x86_64"
        profile.settings["compiler"] = "Visual Studio"

        self.assertEqual('[settings]\narch=x86_64\ncompiler=Visual Studio\ncompiler.version=12',
                         profile.dumps())

    def setting_apply_test(self):
        # Settings
        profile = Profile()
        profile.settings["compiler.version"] = "12"
        profile.settings["arch"] = "x86_64"
        profile.settings["compiler"] = "Visual Studio"

        profile.update_settings({"compiler.version": "14"})

        self.assertEqual('[settings]\narch=x86_64\ncompiler=Visual Studio\ncompiler.version=14',
                         profile.dumps())

