import os
import unittest

from conans.model.profile import Profile
from collections import OrderedDict

from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


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
        profile.settings["compiler"] = "Visual Studio"
        profile.settings["compiler.version"] = "12"

        profile.env_values.add("CXX", "path/to/my/compiler/g++")
        profile.env_values.add("CC", "path/to/my/compiler/gcc")

        profile.scopes["p1"]["conaning"] = "1"
        profile.scopes["p2"]["testing"] = "2"

        profile.build_requires["*"] = ["android_toolchain/1.2.8@lasote/testing"]
        profile.build_requires["zlib/*"] = ["cmake/1.0.2@lasote/stable",
                                            "autotools/1.0.3@lasote/stable"]

        dump = profile.dumps()
        new_profile = Profile.loads(dump)
        self.assertEquals(new_profile.settings, profile.settings)
        self.assertEquals(new_profile.settings["arch"], "x86_64")
        self.assertEquals(new_profile.settings["compiler.version"], "12")
        self.assertEquals(new_profile.settings["compiler"], "Visual Studio")

        self.assertEquals(new_profile.env_values.env_dicts(""), ({'CXX': 'path/to/my/compiler/g++',
                                                                  'CC': 'path/to/my/compiler/gcc'}, {}))

        self.assertEquals(dict(new_profile.scopes)["p1"]["conaning"], '1')
        self.assertEquals(dict(new_profile.scopes)["p2"]["testing"], '2')

        self.assertEquals(new_profile.build_requires["zlib/*"],
                          [ConanFileReference.loads("cmake/1.0.2@lasote/stable"),
                           ConanFileReference.loads("autotools/1.0.3@lasote/stable")])
        self.assertEquals(new_profile.build_requires["*"],
                          [ConanFileReference.loads("android_toolchain/1.2.8@lasote/testing")])

    def profile_settings_update_test(self):
        prof = '''[settings]
os=Windows
'''
        new_profile = Profile.loads(prof)

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
        np = Profile.loads(prof)

        np.update_package_settings({"MyPackage": [("OTHER", "2")]})
        self.assertEquals(np.package_settings_values,
                          {"MyPackage": [("os", "Windows"), ("OTHER", "2")]})

        np.update_package_settings({"MyPackage": [("compiler", "2"), ("compiler.version", "3")]})
        self.assertEquals(np.package_settings_values,
                          {"MyPackage": [("os", "Windows"), ("OTHER", "2"),
                                         ("compiler", "2"), ("compiler.version", "3")]})

    def profile_loads_test(self):
        prof = '''[env]
CXX_FLAGS="-DAAA=0"
[settings]
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile.env_values.env_dicts(""), ({'CXX_FLAGS': '-DAAA=0'}, {}))

        prof = '''[env]
CXX_FLAGS="-DAAA=0"
MyPackage:VAR=1
MyPackage:OTHER=2
OtherPackage:ONE=ONE
[settings]
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile.env_values.env_dicts(""), ({'CXX_FLAGS': '-DAAA=0'}, {}))
        self.assertEquals(new_profile.env_values.env_dicts("MyPackage"), ({"OTHER": "2",
                                                                           "VAR": "1",
                                                                           'CXX_FLAGS': '-DAAA=0'}, {}))

        self.assertEquals(new_profile.env_values.env_dicts("OtherPackage"), ({'CXX_FLAGS': '-DAAA=0',
                                                                              'ONE': 'ONE'}, {}))

        prof = '''[env]
CXX_FLAGS='-DAAA=0'
[settings]
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile.env_values.env_dicts(""), ({'CXX_FLAGS': '-DAAA=0'}, {}))

        prof = '''[env]
CXX_FLAGS=-DAAA=0
[settings]
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile.env_values.env_dicts(""), ({'CXX_FLAGS': '-DAAA=0'}, {}))

        prof = '''[env]
CXX_FLAGS="-DAAA=0
[settings]
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile.env_values.env_dicts(""), ({'CXX_FLAGS': '"-DAAA=0'}, {}))

        prof = '''
[settings]
zlib:compiler=gcc
compiler=Visual Studio
'''
        new_profile = Profile.loads(prof)
        self.assertEquals(new_profile.package_settings["zlib"], {"compiler": "gcc"})
        self.assertEquals(new_profile.settings["compiler"], "Visual Studio")

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

    def profile_loads_win_test(self):
        prof = '''[env]
QTPATH=C:/QtCommercial/5.8/msvc2015_64/bin
QTPATH2="C:/QtCommercial2/5.8/msvc2015_64/bin"
'''
        new_profile = Profile.loads(prof)
        self.assertEqual(new_profile.env_values.data[None]["QTPATH"],
                         "C:/QtCommercial/5.8/msvc2015_64/bin")
        self.assertEqual(new_profile.env_values.data[None]["QTPATH2"],
                         "C:/QtCommercial2/5.8/msvc2015_64/bin")
        self.assertIn("QTPATH=C:/QtCommercial/5.8/msvc2015_64/bin", new_profile.dumps())
        self.assertIn("QTPATH2=C:/QtCommercial2/5.8/msvc2015_64/bin", new_profile.dumps())

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

    def profile_dir_test(self):
        tmp = temp_folder()
        txt = '''
[env]
PYTHONPATH=$PROFILE_DIR/my_python_tools
'''

        def assert_path(profile):
            pythonpath = profile.env_values.env_dicts("")[0]["PYTHONPATH"].replace("/", "\\")
            self.assertEquals(pythonpath, os.path.join(tmp, "my_python_tools").replace("/", "\\"))

        abs_profile_path = os.path.join(tmp, "Myprofile.txt")
        save(abs_profile_path, txt)
        profile = Profile.read_file(abs_profile_path, None, None)
        assert_path(profile)

        profile = Profile.read_file("./Myprofile.txt", tmp, None)
        assert_path(profile)

        profile = Profile.read_file("Myprofile.txt", None, tmp)
        assert_path(profile)
