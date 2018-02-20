import os
import unittest

from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.client.profile_loader import read_profile, ProfileParser
from conans.errors import ConanException
from conans.model.env_info import EnvValues
from conans.test.utils.profiles import create_profile as _create_profile
from conans.test.utils.test_files import temp_folder
from conans.util.files import save, load


def create_profile(folder, name, settings=None, package_settings=None, env=None,
                   package_env=None, options=None):
    _create_profile(folder, name, settings, package_settings, env, package_env, options)
    content = load(os.path.join(folder, name))
    content = "include(default)\n" + content
    save(os.path.join(folder, name), content)


class ProfileParserTest(unittest.TestCase):

    def test_parser(self):
        txt = """
include(a/path/to\profile.txt)
VAR=2
include(other/path/to/file.txt)
OTHERVAR=thing

[settings]
os=2
"""
        a = ProfileParser(txt)
        self.assertEquals(a.vars, {"VAR": "2", "OTHERVAR": "thing"})
        self.assertEquals(a.includes, ["a/path/to\profile.txt", "other/path/to/file.txt"])
        self.assertEquals(a.profile_text, """[settings]
os=2""")

        txt = ""
        a = ProfileParser(txt)
        self.assertEquals(a.vars, {})
        self.assertEquals(a.includes, [])
        self.assertEquals(a.profile_text, "")

        txt = """
include(a/path/to\profile.txt)
VAR=$REPLACE_VAR
include(other/path/to/$FILE)
OTHERVAR=thing

[settings]
os=$OTHERVAR
"""
        a = ProfileParser(txt)
        a.apply_vars({"REPLACE_VAR": "22", "FILE": "MyFile", "OTHERVAR": "thing"})
        self.assertEquals(a.vars, {"VAR": "22", "OTHERVAR": "thing"})
        self.assertEquals(a.includes, ["a/path/to\profile.txt", "other/path/to/MyFile"])
        self.assertEquals(a.profile_text, """[settings]
os=thing""")


conanfile_scope_env = """
import platform
from conans import ConanFile

class AConan(ConanFile):
    name = "Hello0"
    version = "0.1"
    settings = "os", "compiler", "arch"

    def build(self):
        # Print environment vars
        if self.settings.os == "Windows":
            self.run("SET")
        else:
            self.run("env")
"""


class ProfileTest(unittest.TestCase):

    def profile_loads_test(self):

        tmp = temp_folder()

        prof = '''[env]
    CXX_FLAGS="-DAAA=0"
    [settings]
    '''
        new_profile, _ = self._get_profile(tmp, prof)
        self.assertEquals(new_profile.env_values.env_dicts(""), ({'CXX_FLAGS': '-DAAA=0'}, {}))

        prof = '''[env]
    CXX_FLAGS="-DAAA=0"
    MyPackage:VAR=1
    MyPackage:OTHER=2
    OtherPackage:ONE=ONE
    [settings]
    '''
        new_profile, _ = self._get_profile(tmp, prof)
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
        new_profile, _ = self._get_profile(tmp, prof)
        self.assertEquals(new_profile.env_values.env_dicts(""), ({'CXX_FLAGS': '-DAAA=0'}, {}))

        prof = '''[env]
    CXX_FLAGS=-DAAA=0
    [settings]
    '''
        new_profile, _ = self._get_profile(tmp, prof)
        self.assertEquals(new_profile.env_values.env_dicts(""), ({'CXX_FLAGS': '-DAAA=0'}, {}))

        prof = '''[env]
    CXX_FLAGS="-DAAA=0
    [settings]
    '''
        new_profile, _ = self._get_profile(tmp, prof)
        self.assertEquals(new_profile.env_values.env_dicts(""), ({'CXX_FLAGS': '"-DAAA=0'}, {}))

        prof = '''
    [settings]
    zlib:compiler=gcc
    compiler=Visual Studio
    '''
        new_profile, _ = self._get_profile(tmp, prof)
        self.assertEquals(new_profile.package_settings["zlib"], {"compiler": "gcc"})
        self.assertEquals(new_profile.settings["compiler"], "Visual Studio")

    def test_empty_env(self):
        tmp = temp_folder()
        profile, _ = self._get_profile(tmp, "")
        self.assertTrue(isinstance(profile.env_values, EnvValues))

    def test_empty_env_settings(self):
        tmp = temp_folder()
        profile, _ = self._get_profile(tmp, "[settings]")
        self.assertTrue(isinstance(profile.env_values, EnvValues))

    def profile_loads_win_test(self):
        tmp = temp_folder()
        prof = '''[env]
    QTPATH=C:/QtCommercial/5.8/msvc2015_64/bin
    QTPATH2="C:/QtCommercial2/5.8/msvc2015_64/bin"
    '''
        new_profile, _ = self._get_profile(tmp, prof)
        self.assertEqual(new_profile.env_values.data[None]["QTPATH"],
                         "C:/QtCommercial/5.8/msvc2015_64/bin")
        self.assertEqual(new_profile.env_values.data[None]["QTPATH2"],
                         "C:/QtCommercial2/5.8/msvc2015_64/bin")
        self.assertIn("QTPATH=C:/QtCommercial/5.8/msvc2015_64/bin", new_profile.dumps())
        self.assertIn("QTPATH2=C:/QtCommercial2/5.8/msvc2015_64/bin", new_profile.dumps())

    def profile_load_dump_test(self):
        # Empty profile
        tmp = temp_folder()
        profile = Profile()
        dumps = profile.dumps()
        new_profile, _ = self._get_profile(tmp, dumps)
        self.assertEquals(new_profile.settings, profile.settings)

        # Settings
        profile = Profile()
        profile.settings["arch"] = "x86_64"
        profile.settings["compiler"] = "Visual Studio"
        profile.settings["compiler.version"] = "12"

        profile.env_values.add("CXX", "path/to/my/compiler/g++")
        profile.env_values.add("CC", "path/to/my/compiler/gcc")

        profile.build_requires["*"] = ["android_toolchain/1.2.8@lasote/testing"]
        profile.build_requires["zlib/*"] = ["cmake/1.0.2@lasote/stable",
                                            "autotools/1.0.3@lasote/stable"]

        dump = profile.dumps()
        new_profile, _ = self._get_profile(tmp, dump)
        self.assertEquals(new_profile.settings, profile.settings)
        self.assertEquals(new_profile.settings["arch"], "x86_64")
        self.assertEquals(new_profile.settings["compiler.version"], "12")
        self.assertEquals(new_profile.settings["compiler"], "Visual Studio")

        self.assertEquals(new_profile.env_values.env_dicts(""), ({'CXX': 'path/to/my/compiler/g++',
                                                                  'CC': 'path/to/my/compiler/gcc'}, {}))

        self.assertEquals(new_profile.build_requires["zlib/*"],
                          [ConanFileReference.loads("cmake/1.0.2@lasote/stable"),
                           ConanFileReference.loads("autotools/1.0.3@lasote/stable")])
        self.assertEquals(new_profile.build_requires["*"],
                          [ConanFileReference.loads("android_toolchain/1.2.8@lasote/testing")])

    def _get_profile(self, folder, txt):
        abs_profile_path = os.path.join(folder, "Myprofile.txt")
        save(abs_profile_path, txt)
        return read_profile(abs_profile_path, None, None)

    def profile_vars_test(self):
        tmp = temp_folder()

        txt = '''
        MY_MAGIC_VAR=The owls are not

        [env]
        MYVAR=$MY_MAGIC_VAR what they seem.
        '''
        profile, _ = self._get_profile(tmp, txt)
        self.assertEquals("The owls are not what they seem.", profile.env_values.data[None]["MYVAR"])

        # Order in replacement, variable names (simplification of preprocessor)
        txt = '''
                P=Diane, the coffee at the Great Northern
                P2=is delicious

                [env]
                MYVAR=$P2
                '''
        profile, _ = self._get_profile(tmp, txt)
        self.assertEquals("Diane, the coffee at the Great Northern2", profile.env_values.data[None]["MYVAR"])

        # Variables without spaces
        txt = '''
VARIABLE WITH SPACES=12
[env]
MYVAR=$VARIABLE WITH SPACES
                        '''
        with self.assertRaisesRegexp(ConanException, "The names of the variables cannot contain spaces"):
            self._get_profile(tmp, txt)

    def test_profiles_includes(self):
        tmp = temp_folder()

        def save_profile(txt, name):
            abs_profile_path = os.path.join(tmp, name)
            save(abs_profile_path, txt)

        os.mkdir(os.path.join(tmp, "subdir"))

        profile0 = """
ROOTVAR=0


[build_requires]
  one/1.$ROOTVAR@lasote/stable
two/1.2@lasote/stable

"""
        save_profile(profile0, "subdir/profile0.txt")

        profile1 = """
 # Include in subdir, curdir
MYVAR=1
include(./profile0.txt)

[settings]
os=Windows
[options]
zlib:aoption=1
zlib:otheroption=1
[env]
package1:ENVY=$MYVAR
"""

        save_profile(profile1, "subdir/profile1.txt")

        profile2 = """
#  Include in subdir
include(./subdir/profile1.txt)
[settings]
os=$MYVAR
"""

        save_profile(profile2, "profile2.txt")
        profile3 = """
OTHERVAR=34

[build_requires]
one/1.5@lasote/stable


"""
        save_profile(profile3, "profile3.txt")

        profile4 = """
        include(./profile2.txt)
        include(./profile3.txt)

        [env]
        MYVAR=FromProfile3And$OTHERVAR

        [options]
        zlib:otheroption=12

        """

        save_profile(profile4, "profile4.txt")

        profile, variables = read_profile("./profile4.txt", tmp, None)

        self.assertEquals(variables, {"MYVAR": "1", "OTHERVAR": "34", "PROFILE_DIR":
                                      tmp, "ROOTVAR": "0"})
        self.assertEquals("FromProfile3And34", profile.env_values.data[None]["MYVAR"])
        self.assertEquals("1", profile.env_values.data["package1"]["ENVY"])
        self.assertEquals(profile.settings, {"os": "1"})
        self.assertEquals(profile.options.as_list(), [('zlib:aoption', '1'), ('zlib:otheroption', '12')])
        self.assertEquals(profile.build_requires, {"*": [ConanFileReference.loads("one/1.0@lasote/stable"),
                                                         ConanFileReference.loads("two/1.2@lasote/stable"),
                                                         ConanFileReference.loads("one/1.5@lasote/stable")]})

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
        profile, _ = read_profile(abs_profile_path, None, None)
        assert_path(profile)

        profile, _ = read_profile("./Myprofile.txt", tmp, None)
        assert_path(profile)

        profile, _ = read_profile("Myprofile.txt", None, tmp)
        assert_path(profile)
