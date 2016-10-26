import unittest
from conans.model.profile import Profile
from conans.errors import ConanException


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

        profile.env["CXX"] = "path/to/my/compiler/g++"
        profile.env["CC"] = "path/to/my/compiler/gcc"

        profile.scopes["p1"]["conaning"] = "1"
        profile.scopes["p2"]["testing"] = "2"

        dump = profile.dumps()
        new_profile = Profile.loads(dump)
        self.assertEquals(new_profile.settings, profile.settings)
        self.assertEquals(new_profile.settings["arch"], "x86_64")
        self.assertEquals(new_profile.settings["compiler.version"], "12")
        self.assertEquals(new_profile.settings["compiler"], "Visual Studio")

        self.assertEquals(new_profile.env["CXX"], "path/to/my/compiler/g++")
        self.assertEquals(new_profile.env["CC"], "path/to/my/compiler/gcc")

        self.assertEquals(dict(new_profile.scopes)["p1"]["conaning"], '1')
        self.assertEquals(dict(new_profile.scopes)["p2"]["testing"], '2')

    def profile_loads_test(self):
        prof = '''[env]
CXX_FLAGS="-DAAA=0"
[settings]
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile.env["CXX_FLAGS"], "-DAAA=0")

        prof = '''[env]
CXX_FLAGS='-DAAA=0'
[settings]
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile.env["CXX_FLAGS"], "-DAAA=0")

        prof = '''[env]
CXX_FLAGS=-DAAA=0
[settings]
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile.env["CXX_FLAGS"], "-DAAA=0")

        prof = '''[env]
CXX_FLAGS="-DAAA=0
[settings]
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile.env["CXX_FLAGS"], "\"-DAAA=0")

    def profile_dump_order_test(self):
        # Settings
        profile = Profile()
        profile.settings["compiler.version"] = "12"
        profile.settings["arch"] = "x86_64"
        profile.settings["compiler"] = "Visual Studio"

        self.assertEqual('[settings]\narch=x86_64\ncompiler=Visual Studio\ncompiler.version=12\n[scopes]\n[env]',
                         profile.dumps())

    def apply_test(self):
        # Settings
        profile = Profile()
        profile.settings["compiler.version"] = "12"
        profile.settings["arch"] = "x86_64"
        profile.settings["compiler"] = "Visual Studio"

        profile.env["CXX"] = "path/to/my/compiler/g++"
        profile.env["CC"] = "path/to/my/compiler/gcc"

        profile.scopes["p1"]["conaning"] = "True"
        profile.scopes["p2"]["testing"] = "True"

        profile.update_settings({"compiler.version": "14"})

        self.assertEqual('[settings]\narch=x86_64\ncompiler=Visual Studio\ncompiler.version=14\n'
                         '[scopes]\np1:conaning=True\np2:testing=True\n'
                         '[env]\nCC=path/to/my/compiler/gcc\nCXX=path/to/my/compiler/g++',
                         profile.dumps())

        profile.update_scopes({"p1": {"new_one": 2}})
        self.assertEqual('[settings]\narch=x86_64\ncompiler=Visual Studio\ncompiler.version=14\n'
                         '[scopes]\np1:new_one=2\np2:testing=True\n'
                         '[env]\nCC=path/to/my/compiler/gcc\nCXX=path/to/my/compiler/g++',
                         profile.dumps())
