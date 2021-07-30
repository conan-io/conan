import os
import unittest
from collections import OrderedDict

from conans.client.profile_loader import _load_profile
from conans.model.profile import Profile
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class ProfileTest(unittest.TestCase):

    def test_profile_settings_update(self):
        prof = '''[settings]
os=Windows
'''
        new_profile, _ = _load_profile(prof, None, None)

        new_profile.update_settings(OrderedDict([("OTHER", "2")]))
        self.assertEqual(new_profile.settings, OrderedDict([("os", "Windows"), ("OTHER", "2")]))

        new_profile.update_settings(OrderedDict([("compiler", "2"), ("compiler.version", "3")]))
        self.assertEqual(new_profile.settings,
                         OrderedDict([("os", "Windows"), ("OTHER", "2"),
                                      ("compiler", "2"), ("compiler.version", "3")]))

    def test_env_vars_inheritance(self):
        tmp_dir = temp_folder()
        p1 = '''[env]\nVAR=1'''
        p2 = '''include(p1)\n[env]\nVAR=2'''
        save(os.path.join(tmp_dir, "p1"), p1)
        new_profile, _ = _load_profile(p2, tmp_dir, tmp_dir)
        self.assertEqual(new_profile.env_values.data[None]["VAR"], "2")

    def test_profile_subsettings_update(self):
        prof = '''[settings]
os=Windows
compiler=Visual Studio
compiler.runtime=MT
'''
        new_profile, _ = _load_profile(prof, None, None)
        new_profile.update_settings(OrderedDict([("compiler", "gcc")]))
        self.assertEqual(dict(new_profile.settings), {"compiler": "gcc", "os": "Windows"})

        new_profile, _ = _load_profile(prof, None, None)
        new_profile.update_settings(OrderedDict([("compiler", "Visual Studio"),
                                                 ("compiler.subsetting", "3"),
                                                 ("other", "value")]))

        self.assertEqual(dict(new_profile.settings), {"compiler": "Visual Studio",
                                                      "os": "Windows",
                                                      "compiler.runtime": "MT",
                                                      "compiler.subsetting": "3",
                                                      "other": "value"})

    def test_package_settings_update(self):
        prof = '''[settings]
MyPackage:os=Windows

    # In the previous line there are some spaces
'''
        np, _ = _load_profile(prof, None, None)

        np.update_package_settings({"MyPackage": [("OTHER", "2")]})
        self.assertEqual(np.package_settings_values,
                         {"MyPackage": [("os", "Windows"), ("OTHER", "2")]})

        np._package_settings_values = None  # invalidate caching
        np.update_package_settings({"MyPackage": [("compiler", "2"), ("compiler.version", "3")]})
        self.assertEqual(np.package_settings_values,
                         {"MyPackage": [("os", "Windows"), ("OTHER", "2"),
                                        ("compiler", "2"), ("compiler.version", "3")]})

    def test_profile_dump_order(self):
        # Settings
        profile = Profile()
        profile.package_settings["zlib"] = {"compiler": "gcc"}
        profile.settings["arch"] = "x86_64"
        profile.settings["compiler"] = "Visual Studio"
        profile.settings["compiler.version"] = "12"
        profile.build_requires["*"] = ["zlib/1.2.8@lasote/testing"]
        profile.build_requires["zlib/*"] = ["aaaa/1.2.3@lasote/testing", "bb/1.2@lasote/testing"]
        self.assertEqual("""[settings]
arch=x86_64
compiler=Visual Studio
compiler.version=12
zlib:compiler=gcc
[options]
[build_requires]
*: zlib/1.2.8@lasote/testing
zlib/*: aaaa/1.2.3@lasote/testing, bb/1.2@lasote/testing
[env]""".splitlines(), profile.dumps().splitlines())

    def test_apply(self):
        # Settings
        profile = Profile()
        profile.settings["arch"] = "x86_64"
        profile.settings["compiler"] = "Visual Studio"
        profile.settings["compiler.version"] = "12"

        profile.env_values.add("CXX", "path/to/my/compiler/g++")
        profile.env_values.add("CC", "path/to/my/compiler/gcc")

        profile.update_settings(OrderedDict([("compiler.version", "14")]))

        self.assertEqual('[settings]\narch=x86_64\ncompiler=Visual Studio'
                         '\ncompiler.version=14\n'
                         '[options]\n'
                         '[build_requires]\n'
                         '[env]\nCC=path/to/my/compiler/gcc\nCXX=path/to/my/compiler/g++',
                         profile.dumps())


def test_update_build_requires():
    # https://github.com/conan-io/conan/issues/8205#issuecomment-775032229
    profile = Profile()
    profile.build_requires["*"] = ["zlib/1.2.8"]

    profile2 = Profile()
    profile2.build_requires["*"] = ["zlib/1.2.8"]

    profile.compose_profile(profile2)
    assert profile.build_requires["*"] == ["zlib/1.2.8"]

    profile3 = Profile()
    profile3.build_requires["*"] = ["zlib/1.2.11"]

    profile.compose_profile(profile3)
    assert profile.build_requires["*"] == ["zlib/1.2.11"]

    profile4 = Profile()
    profile4.build_requires["*"] = ["cmake/2.7"]

    profile.compose_profile(profile4)
    assert profile.build_requires["*"] == ["zlib/1.2.11", "cmake/2.7"]
