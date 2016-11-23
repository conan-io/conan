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
        profile._settings["arch"] = "x86_64"
        profile._settings["compiler.version"] = "12"
        profile._settings["compiler"] = "Visual Studio"

        profile._env["CXX"] = "path/to/my/compiler/g++"
        profile._env["CC"] = "path/to/my/compiler/gcc"

        profile.scopes["p1"]["conaning"] = "1"
        profile.scopes["p2"]["testing"] = "2"

        dump = profile.dumps()
        new_profile = Profile.loads(dump)
        self.assertEquals(new_profile.settings, profile.settings)
        self.assertEquals(new_profile._settings["arch"], "x86_64")
        self.assertEquals(new_profile._settings["compiler.version"], "12")
        self.assertEquals(new_profile._settings["compiler"], "Visual Studio")

        self.assertEquals(new_profile._env["CXX"], "path/to/my/compiler/g++")
        self.assertEquals(new_profile._env["CC"], "path/to/my/compiler/gcc")

        self.assertEquals(dict(new_profile.scopes)["p1"]["conaning"], '1')
        self.assertEquals(dict(new_profile.scopes)["p2"]["testing"], '2')

    def profile_settings_update_test(self):
        prof = '''[settings]
os=Windows
'''
        new_profile = Profile.loads(prof)

        new_profile.update_settings([("OTHER", "2")])
        self.assertEquals(new_profile.settings, [("os", "Windows"), ("OTHER", "2")])

        new_profile.update_settings([("compiler.version", "3"), ("compiler", "2")])
        self.assertEquals(new_profile.settings, [("os", "Windows"), ("OTHER", "2"),
                                                 ("compiler", "2"), ("compiler.version", "3")])

    def package_settings_update_test(self):
        prof = '''[settings]
MyPackage:os=Windows
'''
        np = Profile.loads(prof)

        np.update_package_settings({"MyPackage": [("OTHER", "2")]})
        self.assertEquals(np.package_settings, {"MyPackage": [("os", "Windows"), ("OTHER", "2")]})

        np.update_package_settings({"MyPackage": [("compiler.version", "3"), ("compiler", "2")]})
        self.assertEquals(np.package_settings, {"MyPackage":
                                                [("os", "Windows"), ("OTHER", "2"),
                                                 ("compiler", "2"), ("compiler.version", "3")]})

    def profile_env_update_test(self):
        prof = '''[env]
CXX_FLAGS="-DAAA=0"
[settings]
'''
        new_profile = Profile.loads(prof)

        new_profile.update_env([("OTHER", "2")])
        self.assertEquals(new_profile.env, [("OTHER", "2"), ("CXX_FLAGS", "-DAAA=0")])

        new_profile.update_env([("OTHER", "3"), ("NEW", "4")])
        self.assertEquals(new_profile.env, [("OTHER", "3"), ("NEW", "4"), ("CXX_FLAGS", "-DAAA=0")])

        new_profile.update_env([("NEW", "4"), ("CXX_FLAGS", "A")])
        self.assertEquals(new_profile.env, [("NEW", "4"), ("CXX_FLAGS", "A"), ("OTHER", "3")])

    def profile_package_env_update_test(self):
        prof = '''[env]
MyPackage:VARIABLE=2
[settings]
'''
        new_profile = Profile.loads(prof)

        new_profile.update_packages_env({"MyPackage": [("VARIABLE", "3")]})
        self.assertEquals(new_profile.package_env["MyPackage"], [("VARIABLE", "3")])

        new_profile.update_packages_env({"MyPackage": [("OTHER", "2")]})
        self.assertEquals(new_profile.package_env["MyPackage"], [("OTHER", "2"), ("VARIABLE", "3")])

        new_profile.update_packages_env({"MyPackage": [("SOME", "VAR"), ("OTHER", "22")]})
        self.assertEquals(new_profile.package_env["MyPackage"], [("SOME", "VAR"), ("OTHER", "22"), ("VARIABLE", "3")])

        new_profile.update_packages_env({"OtherPackage": [("ONE", "2")]})
        self.assertEquals(new_profile.package_env["MyPackage"], [("SOME", "VAR"), ("OTHER", "22"), ("VARIABLE", "3")])
        self.assertEquals(new_profile.package_env["OtherPackage"], [("ONE", "2")])

    def profile_loads_test(self):
        prof = '''[env]
CXX_FLAGS="-DAAA=0"
[settings]
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile.env, [("CXX_FLAGS", "-DAAA=0")])

        prof = '''[env]
CXX_FLAGS="-DAAA=0"
MyPackage:VAR=1
MyPackage:OTHER=2
OtherPackage:ONE=ONE
[settings]
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile.env, [("CXX_FLAGS", "-DAAA=0")])
        self.assertEquals(new_profile.package_env, {"MyPackage": [("VAR", "1"), ("OTHER", "2")],
                                                    "OtherPackage": [("ONE", "ONE")]})

        prof = '''[env]
CXX_FLAGS='-DAAA=0'
[settings]
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile.env, [("CXX_FLAGS", "-DAAA=0")])

        prof = '''[env]
CXX_FLAGS=-DAAA=0
[settings]
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile.env, [("CXX_FLAGS", "-DAAA=0")])

        prof = '''[env]
CXX_FLAGS="-DAAA=0
[settings]
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile.env, [("CXX_FLAGS", "\"-DAAA=0")])

        prof = '''
[settings]
zlib:compiler=gcc
compiler=Visual Studio
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile._package_settings["zlib"], {"compiler": "gcc"})
        self.assertEquals(new_profile._settings["compiler"], "Visual Studio")

    def profile_dump_order_test(self):
        # Settings
        profile = Profile()
        profile._package_settings["zlib"] = {"compiler": "gcc"}
        profile._settings["compiler.version"] = "12"
        profile._settings["arch"] = "x86_64"
        profile._settings["compiler"] = "Visual Studio"

        self.assertEqual('[settings]\narch=x86_64\ncompiler=Visual Studio\ncompiler.version=12\nzlib:compiler=gcc\n[scopes]\n[env]',
                         profile.dumps())

    def apply_test(self):
        # Settings
        profile = Profile()
        profile._settings["compiler.version"] = "12"
        profile._settings["arch"] = "x86_64"
        profile._settings["compiler"] = "Visual Studio"

        profile._env["CXX"] = "path/to/my/compiler/g++"
        profile._env["CC"] = "path/to/my/compiler/gcc"

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
