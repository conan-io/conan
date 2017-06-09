import os
import unittest

from conans.client.profile_loader import _load_profile, read_profile
from conans.model.profile import Profile
from collections import OrderedDict

from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class ProfileTest(unittest.TestCase):


    def profile_settings_update_test(self):
        prof = '''[settings]
os=Windows
'''
        new_profile, _ = _load_profile(prof, None, None)

        new_profile.update_settings([("OTHER", "2")])
        self.assertEquals(new_profile.settings, OrderedDict([("os", "Windows"), ("OTHER", "2")]))

        new_profile.update_settings([("compiler", "2"), ("compiler.version", "3")])
        self.assertEquals(new_profile.settings,
                          OrderedDict([("os", "Windows"), ("OTHER", "2"),
                                       ("compiler", "2"), ("compiler.version", "3")]))

    def package_settings_update_test(self):
        prof = '''[settings]
MyPackage:os=Windows
'''
        np , _ = _load_profile(prof, None, None)

        np.update_package_settings({"MyPackage": [("OTHER", "2")]})
        self.assertEquals(np.package_settings_values,
                          {"MyPackage": [("os", "Windows"), ("OTHER", "2")]})

        np.update_package_settings({"MyPackage": [("compiler", "2"), ("compiler.version", "3")]})
        self.assertEquals(np.package_settings_values,
                          {"MyPackage": [("os", "Windows"), ("OTHER", "2"),
                                         ("compiler", "2"), ("compiler.version", "3")]})

    def profile_dump_order_test(self):
        # Settings
        profile = Profile()
        profile.package_settings["zlib"] = {"compiler": "gcc"}
        profile.settings["arch"] = "x86_64"
        profile.settings["compiler"] = "Visual Studio"
        profile.settings["compiler.version"] = "12"
        profile.build_requires["*"] = ["zlib/1.2.8@lasote/testing"]
        profile.build_requires["zlib/*"] = ["aaaa/1.2.3@lasote/testing", "bb/1.2@lasote/testing"]
        self.assertEqual("""[build_requires]
*: zlib/1.2.8@lasote/testing
zlib/*: aaaa/1.2.3@lasote/testing, bb/1.2@lasote/testing
[settings]
arch=x86_64
compiler=Visual Studio
compiler.version=12
zlib:compiler=gcc
[options]
[scopes]
[env]""".splitlines(), profile.dumps().splitlines())

    def apply_test(self):
        # Settings
        profile = Profile()
        profile.settings["arch"] = "x86_64"
        profile.settings["compiler"] = "Visual Studio"
        profile.settings["compiler.version"] = "12"

        profile.env_values.add("CXX", "path/to/my/compiler/g++")
        profile.env_values.add("CC", "path/to/my/compiler/gcc")

        profile.scopes["p1"]["conaning"] = "True"
        profile.scopes["p2"]["testing"] = "True"

        profile.update_settings({"compiler.version": "14"})

        self.assertEqual('[build_requires]\n[settings]\narch=x86_64\ncompiler=Visual Studio\ncompiler.version=14\n'
                         '[options]\n[scopes]\np1:conaning=True\np2:testing=True\n'
                         '[env]\nCC=path/to/my/compiler/gcc\nCXX=path/to/my/compiler/g++',
                         profile.dumps())

        profile.update_scopes({"p1": {"new_one": 2}})
        self.assertEqual('[build_requires]\n[settings]\narch=x86_64\ncompiler=Visual Studio\ncompiler.version=14\n'
                         '[options]\n[scopes]\np1:new_one=2\np2:testing=True\n'
                         '[env]\nCC=path/to/my/compiler/gcc\nCXX=path/to/my/compiler/g++',
                         profile.dumps())
