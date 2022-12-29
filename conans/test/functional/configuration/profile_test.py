import json
import os
import platform
import textwrap
import unittest
from collections import OrderedDict
from textwrap import dedent

import pytest
from parameterized import parameterized

from conans.client import tools
from conans.paths import CONANFILE
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.profiles import create_profile as _create_profile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.test.utils.mocks import TestBufferConanOutput
from conans.util.files import load, save

conanfile_scope_env = """
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


def create_profile(folder, name, settings=None, package_settings=None, env=None,
                   package_env=None, options=None):
    _create_profile(folder, name, settings, package_settings, env, package_env, options)
    content = load(os.path.join(folder, name))
    content = "include(default)\n    \n" + content
    save(os.path.join(folder, name), content)


class ProfileTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def test_profile_conanfile_txt(self):
        """
        Test prepended env variables are applied correctrly from a profile
        """
        self.client.save({"conanfile.txt": ""})
        create_profile(self.client.cache.profiles_path, "envs", settings={},
                       env=[("A_VAR", "A_VALUE"), ("PREPEND_VAR", ["new_path", "other_path"])],
                       package_env={"Hello0": [("OTHER_VAR", "2")]})
        self.client.run("install . -pr envs -g virtualenv")
        content = self.client.load("environment.sh.env")
        self.assertIn(":".join(["PREPEND_VAR=\"new_path\"", "\"other_path\""]) +
                      "${PREPEND_VAR:+:$PREPEND_VAR}", content)
        if platform.system() == "Windows":
            content = self.client.load("environment.bat.env")
            self.assertIn(";".join(["PREPEND_VAR=new_path", "other_path", "%PREPEND_VAR%"]),
                          content)

    def test_profile_relative_cwd(self):
        self.client.save({"conanfile.txt": "", "sub/sub/profile": ""})
        self.client.current_folder = os.path.join(self.client.current_folder, "sub")
        self.client.run("install .. -pr=sub/profile2", assert_error=True)
        self.assertIn("ERROR: Profile not found: sub/profile2", self.client.out)
        self.client.run("install .. -pr=sub/profile")
        self.assertIn("conanfile.txt: Installing package", self.client.out)

    def test_base_profile_generated(self):
        """we are testing that the default profile is created (when not existing, fresh install)
         even when you run a create with a profile"""
        self.client.save({CONANFILE: conanfile_scope_env,
                          "myprofile": "include(default)\n[settings]\nbuild_type=Debug"})
        self.client.run("create . conan/testing --profile myprofile")

    def test_bad_syntax(self):
        self.client.save({CONANFILE: conanfile_scope_env})
        self.client.run("export . lasote/stable")

        profile = '''
        [settings
        '''
        clang_profile_path = os.path.join(self.client.cache.profiles_path, "clang")
        save(clang_profile_path, profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang",
                        assert_error=True)
        self.assertIn("Error reading 'clang' profile", self.client.out)
        self.assertIn("Bad syntax", self.client.out)

        profile = '''
        [settings]
        [invented]
        '''
        save(clang_profile_path, profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang",
                        assert_error=True)
        self.assertIn("Unrecognized field 'invented'", self.client.out)
        self.assertIn("Error reading 'clang' profile", self.client.out)

        profile = '''
        [settings]
        as
        '''
        save(clang_profile_path, profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang",
                        assert_error=True)
        self.assertIn("Error reading 'clang' profile: Invalid setting line 'as'",
                      self.client.out)

        profile = '''
        [env]
        as
        '''
        save(clang_profile_path, profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang",
                        assert_error=True)
        self.assertIn("Error reading 'clang' profile: Invalid env line 'as'",
                      self.client.out)

        profile = '''
        [settings]
        os =   a value
        '''
        save(clang_profile_path, profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang",
                        assert_error=True)
        # stripped "a value"
        self.assertIn("'a value' is not a valid 'settings.os'", self.client.out)

        profile = '''
        include(default)
        [env]
        ENV_VAR =   a value
        '''
        save(clang_profile_path, profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang")
        self._assert_env_variable_printed("ENV_VAR", "a value")

        profile = '''
        include(default)
        # Line with comments is not a problem
        [env]
        # Not even here
        ENV_VAR =   a value
        '''
        save(clang_profile_path, profile)
        self.client.run("install Hello0/0.1@lasote/stable --build -pr clang")
        self._assert_env_variable_printed("ENV_VAR", "a value")

    @parameterized.expand([("", ), ("./local_profiles/", ), (None, )])
    def test_install_with_missing_profile(self, path):
        if path is None:
            # Not good practice to introduce temp_folder() in the expand because it randomize
            # the test names causing issues to split them in N processes
            path = temp_folder() + "/"
        self.client.save({CONANFILE: conanfile_scope_env})
        self.client.run('install . -pr "%sscopes_env"' % path, assert_error=True)
        self.assertIn("ERROR: Profile not found:", self.client.out)
        self.assertIn("scopes_env", self.client.out)

    def test_install_profile_env(self):
        create_profile(self.client.cache.profiles_path, "envs", settings={},
                       env=[("A_VAR", "A_VALUE"),
                            ("PREPEND_VAR", ["new_path", "other_path"])],
                       package_env={"Hello0": [("OTHER_VAR", "2")]})

        self.client.save({"conanfile.py": conanfile_scope_env})
        self.client.run("export . lasote/stable")
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr envs")
        self._assert_env_variable_printed("PREPEND_VAR",
                                          os.pathsep.join(["new_path", "other_path"]))
        self.assertEqual(1, str(self.client.out).count("PREPEND_VAR=new_path"))  # prepended once
        self._assert_env_variable_printed("A_VAR", "A_VALUE")
        self._assert_env_variable_printed("OTHER_VAR", "2")

        # Override with package var
        self.client.run("install Hello0/0.1@lasote/stable --build "
                        "-pr envs -e Hello0:A_VAR=OTHER_VALUE")
        self._assert_env_variable_printed("A_VAR", "OTHER_VALUE")
        self._assert_env_variable_printed("OTHER_VAR", "2")

        # Override package var with package var
        self.client.run("install Hello0/0.1@lasote/stable --build -pr envs "
                        "-e Hello0:A_VAR=OTHER_VALUE -e Hello0:OTHER_VAR=3")
        self._assert_env_variable_printed("A_VAR", "OTHER_VALUE")
        self._assert_env_variable_printed("OTHER_VAR", "3")

        # Pass a variable with "=" symbol
        self.client.run("install Hello0/0.1@lasote/stable --build -pr envs "
                        "-e Hello0:A_VAR=Valuewith=equal -e Hello0:OTHER_VAR=3")
        self._assert_env_variable_printed("A_VAR", "Valuewith=equal")
        self._assert_env_variable_printed("OTHER_VAR", "3")

    def test_install_profile_settings(self):
        # Create a profile and use it
        profile_settings = OrderedDict([("compiler", "Visual Studio"),
                                        ("compiler.version", "12"),
                                        ("compiler.runtime", "MD"),
                                        ("arch", "x86")])

        create_profile(self.client.cache.profiles_path, "vs_12_86",
                       settings=profile_settings, package_settings={})

        self.client.cache.default_profile  # Creates default
        tools.replace_in_file(self.client.cache.default_profile_path,
                              "compiler.libcxx", "#compiler.libcxx", strict=False,
                              output=TestBufferConanOutput())

        self.client.save({"conanfile.py": conanfile_scope_env})
        self.client.run("export . lasote/stable")
        self.client.run("install . --build missing -pr vs_12_86")
        info = self.client.load("conaninfo.txt")
        for setting, value in profile_settings.items():
            self.assertIn("%s=%s" % (setting, value), info)

        # Try to override some settings in install command
        self.client.run("install . --build missing -pr vs_12_86 -s compiler.version=14")
        info = self.client.load("conaninfo.txt")
        for setting, value in profile_settings.items():
            if setting != "compiler.version":
                self.assertIn("%s=%s" % (setting, value), info)
            else:
                self.assertIn("compiler.version=14", info)

        # Use package settings in profile
        tmp_settings = OrderedDict()
        tmp_settings["compiler"] = "gcc"
        tmp_settings["compiler.libcxx"] = "libstdc++11"
        tmp_settings["compiler.version"] = "4.8"
        package_settings = {"Hello0": tmp_settings}
        create_profile(self.client.cache.profiles_path,
                       "vs_12_86_Hello0_gcc", settings=profile_settings,
                       package_settings=package_settings)
        # Try to override some settings in install command
        self.client.run("install . --build missing -pr vs_12_86_Hello0_gcc -s compiler.version=14")
        info = self.client.load("conaninfo.txt")
        self.assertIn("compiler=gcc", info)
        self.assertIn("compiler.libcxx=libstdc++11", info)

        # If other package is specified compiler is not modified
        package_settings = {"NoExistsRecipe": tmp_settings}
        create_profile(self.client.cache.profiles_path,
                       "vs_12_86_Hello0_gcc", settings=profile_settings,
                       package_settings=package_settings)
        # Try to override some settings in install command
        self.client.run("install . --build missing -pr vs_12_86_Hello0_gcc -s compiler.version=14")
        info = self.client.load("conaninfo.txt")
        self.assertIn("compiler=Visual Studio", info)
        self.assertNotIn("compiler.libcxx", info)

        # Mix command line package settings with profile
        package_settings = {"Hello0": tmp_settings}
        create_profile(self.client.cache.profiles_path, "vs_12_86_Hello0_gcc",
                       settings=profile_settings, package_settings=package_settings)

        # Try to override some settings in install command
        self.client.run("install . --build missing -pr vs_12_86_Hello0_gcc"
                        " -s compiler.version=14 -s Hello0:compiler.libcxx=libstdc++")
        info = self.client.load("conaninfo.txt")
        self.assertIn("compiler=gcc", info)
        self.assertNotIn("compiler.libcxx=libstdc++11", info)
        self.assertIn("compiler.libcxx=libstdc++", info)

    def test_install_profile_package_settings(self):
        self.client.save({"conanfile.py": conanfile_scope_env})

        # Create a profile and use it
        profile_settings = OrderedDict([("os", "Windows"),
                                        ("compiler", "Visual Studio"),
                                        ("compiler.version", "12"),
                                        ("compiler.runtime", "MD"),
                                        ("arch", "x86")])

        # Use package settings in profile
        tmp_settings = OrderedDict()
        tmp_settings["compiler"] = "gcc"
        tmp_settings["compiler.libcxx"] = "libstdc++11"
        tmp_settings["compiler.version"] = "4.8"
        package_settings = {"*@lasote/*": tmp_settings}
        _create_profile(self.client.cache.profiles_path,
                        "myprofile", settings=profile_settings,
                        package_settings=package_settings)
        # Try to override some settings in install command
        self.client.run("install . lasote/testing -pr myprofile")
        info = self.client.load("conaninfo.txt")
        self.assertIn("compiler=gcc", info)
        self.assertIn("compiler.libcxx=libstdc++11", info)
        self.assertIn("compiler.version=4.8", info)

        package_settings = {"*@other/*": tmp_settings}
        _create_profile(self.client.cache.profiles_path,
                        "myprofile", settings=profile_settings,
                        package_settings=package_settings)
        # Try to override some settings in install command
        self.client.run("install . lasote/testing -pr myprofile")
        info = self.client.load("conaninfo.txt")
        self.assertIn("compiler=Visual Studio", info)
        self.assertIn("compiler.runtime=MD", info)
        self.assertIn("compiler.version=12", info)
        self.assertNotIn("gcc", info)
        self.assertNotIn("libcxx", info)

    def test_package_settings_no_user_channel(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                settings = "os"
                def build(self):
                    self.output.info("SETTINGS! os={}!!".format(self.settings.os))
                """)
        profile = textwrap.dedent("""
            [settings]
            os=Windows
            # THIS FAILED BEFORE WITH NO MATCH
            mypkg/0.1:os=Linux
            mypkg/0.1@user/channel:os=FreeBSD
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "profile": profile})

        client.run("create . mypkg/0.1@user/channel -pr=profile")
        assert "mypkg/0.1@user/channel: SETTINGS! os=FreeBSD!!" in client.out
        client.run("create . mypkg/0.1@ -pr=profile")
        assert "mypkg/0.1: SETTINGS! os=Linux!!" in client.out

    def test_install_profile_options(self):
        create_profile(self.client.cache.profiles_path, "vs_12_86",
                       options=[("Hello0:language", 1),
                                ("Hello0:static", False)])

        self.client.save({"conanfile.py": GenConanfile("Hello0", "1").with_option("language", [1, 2])
                          .with_option("static", [True, False])})
        self.client.run("install . --build missing -pr vs_12_86")
        info = self.client.load("conaninfo.txt")
        self.assertIn("language=1", info)
        self.assertIn("static=False", info)

    def test_scopes_env(self):
        # Create a profile and use it
        create_profile(self.client.cache.profiles_path, "scopes_env", settings={},
                       env=[("CXX", "/path/tomy/g++"), ("CC", "/path/tomy/gcc")])
        self.client.save({CONANFILE: conanfile_scope_env})
        self.client.run("export . lasote/stable")
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr scopes_env")

        self._assert_env_variable_printed("CC", "/path/tomy/gcc")
        self._assert_env_variable_printed("CXX", "/path/tomy/g++")

        # The env variable shouldn't persist after install command
        self.assertFalse(os.environ.get("CC", None) == "/path/tomy/gcc")
        self.assertFalse(os.environ.get("CXX", None) == "/path/tomy/g++")

    def test_default_including_another_profile(self):
        p1 = "include(p2)\n[env]\nA_VAR=1"
        p2 = "include(default)\n[env]\nA_VAR=2"
        self.client.cache.config  # Create the default conf
        self.client.cache.default_profile  # Create default profile
        save(os.path.join(self.client.cache.profiles_path, "p1"), p1)
        save(os.path.join(self.client.cache.profiles_path, "p2"), p2)
        # Change default profile to p1 => p2 => default
        tools.replace_in_file(self.client.cache.conan_conf_path,
                              "default_profile = default",
                              "default_profile = p1",
                              output=TestBufferConanOutput())
        self.client.save({CONANFILE: conanfile_scope_env})
        self.client.run("create . user/testing")
        self._assert_env_variable_printed("A_VAR", "1")

    def test_test_package(self):
        test_conanfile = '''from conans.model.conan_file import ConanFile
from conans import CMake
import os

class DefaultNameConan(ConanFile):
    name = "DefaultName"
    version = "0.1"
    settings = "os", "compiler", "arch", "build_type"
    requires = "Hello0/0.1@lasote/stable"

    def build(self):
        # Print environment vars
        if self.settings.os == "Windows":
            self.run('echo "My var is %ONE_VAR%"')
        else:
            self.run('echo "My var is $ONE_VAR"')

    def test(self):
        pass

'''
        files = {"conanfile.py": conanfile_scope_env,
                 "test_package/conanfile.py": test_conanfile}
        # Create a profile and use it
        create_profile(self.client.cache.profiles_path, "scopes_env", settings={},
                       env=[("ONE_VAR", "ONE_VALUE")])

        self.client.save(files)
        self.client.run("create . lasote/stable --profile scopes_env")

        self._assert_env_variable_printed("ONE_VAR", "ONE_VALUE")
        self.assertIn("My var is ONE_VALUE", str(self.client.out))

        # Try now with package environment vars
        create_profile(self.client.cache.profiles_path, "scopes_env2", settings={},
                       package_env={"DefaultName": [("ONE_VAR", "IN_TEST_PACKAGE")],
                                    "Hello0": [("ONE_VAR", "PACKAGE VALUE")]})

        self.client.run("create . lasote/stable --profile scopes_env2")

        self._assert_env_variable_printed("ONE_VAR", "PACKAGE VALUE")
        self.assertIn("My var is IN_TEST_PACKAGE", str(self.client.out))

        # Try now overriding some variables with command line
        self.client.run("create . lasote/stable --profile scopes_env2 "
                        "-e DefaultName:ONE_VAR=InTestPackageOverride "
                        "-e Hello0:ONE_VAR=PackageValueOverride ")

        self._assert_env_variable_printed("ONE_VAR", "PackageValueOverride")
        self.assertIn("My var is InTestPackageOverride", str(self.client.out))

        # A global setting in command line won't override a scoped package variable
        self.client.run("create . lasote/stable --profile scopes_env2 -e ONE_VAR=AnotherValue")
        self._assert_env_variable_printed("ONE_VAR", "PACKAGE VALUE")

    def _assert_env_variable_printed(self, name, value):
        self.assertIn("%s=%s" % (name, value), self.client.out)

    def test_info_with_profiles(self):

        self.client.run("remove '*' -f")
        # Create a simple recipe to require
        winreq_conanfile = '''
from conans.model.conan_file import ConanFile

class WinRequireDefaultNameConan(ConanFile):
    name = "WinRequire"
    version = "0.1"
    settings = "os", "compiler", "arch", "build_type"

'''

        files = {"conanfile.py": winreq_conanfile}
        self.client.save(files)
        self.client.run("export . lasote/stable")

        # Now require the first recipe depending on OS=windows
        conanfile = '''from conans.model.conan_file import ConanFile
import os

class DefaultNameConan(ConanFile):
    name = "Hello"
    version = "0.1"
    settings = "os", "compiler", "arch", "build_type"

    def config(self):
        if self.settings.os == "Windows":
            self.requires.add("WinRequire/0.1@lasote/stable")

'''
        files = {"conanfile.py": conanfile}
        self.client.save(files)
        self.client.run("export . lasote/stable")

        # Create a profile that doesn't activate the require
        create_profile(self.client.cache.profiles_path, "scopes_env",
                       settings={"os": "Linux"})

        # Install with the previous profile
        self.client.run("info Hello/0.1@lasote/stable --profile scopes_env")
        self.assertNotIn('''Requires:
                WinRequire/0.1@lasote/stable''', self.client.out)

        # Create a profile that activate the require
        create_profile(self.client.cache.profiles_path, "scopes_env",
                       settings={"os": "Windows"})

        # Install with the previous profile
        self.client.run("info Hello/0.1@lasote/stable --profile scopes_env")
        self.assertIn('''Requires:
        WinRequire/0.1@lasote/stable''', self.client.out)


class ProfileAggregationTest(unittest.TestCase):

    profile1 = dedent("""
    [settings]
    os=Windows
    arch=x86_64

    [env]
    ENV1=foo
    ENV2=bar

    """)

    profile2 = dedent("""
    [settings]
    arch=x86
    build_type=Debug
    compiler=Visual Studio
    compiler.version=15

    [env]
    ENV1=foo2
    ENV3=bar2
    """)

    conanfile = dedent("""
    from conans.model.conan_file import ConanFile
    import os

    class DefaultNameConan(ConanFile):
        settings = "os", "compiler", "arch", "build_type"

        def build(self):
            self.output.warn("ENV1:%s" % os.getenv("ENV1"))
            self.output.warn("ENV2:%s" % os.getenv("ENV2"))
            self.output.warn("ENV3:%s" % os.getenv("ENV3"))
    """)

    consumer = dedent("""
    from conans.model.conan_file import ConanFile
    import os

    class DefaultNameConan(ConanFile):
        settings = "os", "compiler", "arch", "build_type"
        requires = "lib/1.0@user/channel"
    """)

    def setUp(self):
        self.client = TestClient()
        self.client.save({CONANFILE: self.conanfile,
                          "profile1": self.profile1, "profile2": self.profile2})

    def test_create(self):

        # The latest declared profile has priority
        self.client.run("create . lib/1.0@user/channel --profile profile1 -pr profile2")
        self.assertIn(dedent("""
        [env]
        ENV1=foo2
        ENV2=bar
        ENV3=bar2
        """), self.client.out)
        self.client.run("search lib/1.0@user/channel")
        self.assertIn("arch: x86", self.client.out)

    def test_info(self):

        # The latest declared profile has priority
        self.client.run("create . lib/1.0@user/channel --profile profile1 -pr profile2")

        self.client.save({CONANFILE: self.consumer})
        self.client.run("info . --profile profile1 --profile profile2")
        self.assertIn("b786e9ece960c3a76378ca4d5b0d0e922f4cedc1", self.client.out)

        # Build order
        self.client.run("info . --profile profile1 --profile profile2 "
                        "--build-order lib/1.0@user/channel")
        self.assertIn("[lib/1.0@user/channel]", self.client.out)

    def test_install(self):
        self.client.run("export . lib/1.0@user/channel")
        # Install ref
        self.client.run("install lib/1.0@user/channel -pr profile1 -pr profile2 --build missing")
        self.assertIn(dedent("""
               [env]
               ENV1=foo2
               ENV2=bar
               ENV3=bar2
               """), self.client.out)
        self.client.run("search lib/1.0@user/channel")
        self.assertIn("arch: x86", self.client.out)

        # Install project
        self.client.save({CONANFILE: self.consumer})
        self.client.run("install . -pr profile1 -pr profile2 --build")
        self.assertIn("arch=x86", self.client.out)
        self.assertIn(dedent("""
                       [env]
                       ENV1=foo2
                       ENV2=bar
                       ENV3=bar2
                       """), self.client.out)

    def test_export_pkg(self):
        self.client.run("export-pkg . lib/1.0@user/channel -pr profile1 -pr profile2")
        # ID for the expected settings applied: x86, Visual Studio 15,...
        self.assertIn("b786e9ece960c3a76378ca4d5b0d0e922f4cedc1", self.client.out)

    def test_profile_crazy_inheritance(self):
        profile1 = dedent("""
            [settings]
            os=Windows
            arch=x86_64
            compiler=Visual Studio
            compiler.version=15
            """)

        profile2 = dedent("""
            include(profile1)
            [settings]
            os=Linux
            """)

        self.client.save({"profile1": profile1, "profile2": profile2})
        self.client.run("create . lib/1.0@user/channel --profile profile2 -pr profile1")
        self.assertIn(dedent("""
                             Configuration:
                             [settings]
                             arch=x86_64
                             compiler=Visual Studio
                             compiler.runtime=MD
                             compiler.version=15
                             os=Windows"""), self.client.out)


def test_profile_from_cache_path():
    """ When passing relative folder/profile as profile file, it MUST be used
        conan install . -pr=profiles/default
        /tmp/profiles/default MUST be consumed as target profile
        https://github.com/conan-io/conan/pull/8685
    """
    client = TestClient()
    path = os.path.join(client.cache.profiles_path, "android", "profile1")
    save(path, "[settings]\nos=Android")
    client.save({"conanfile.txt": ""})
    client.run("install . -pr=android/profile1")
    assert "os=Android" in client.out


def test_profile_from_relative_pardir():
    """ When passing relative ../path as profile file, it MUST be used
        conan install . -pr=../profiles/default
        /tmp/profiles/default MUST be consumed as target profile
    """
    client = TestClient()
    client.save({"profiles/default": "[settings]\nos=AIX",
                 "current/conanfile.txt": ""})
    with client.chdir("current"):
        client.run("install . -pr=../profiles/default")
    assert "os=AIX" in client.out


def test_profile_from_relative_dotdir():
    """ When passing relative ./path as profile file, it MUST be used
        conan install . -pr=./profiles/default
        /tmp/profiles/default MUST be consumed as target profile
    """
    client = TestClient()
    client.save({os.path.join("profiles", "default"): "[settings]\nos=AIX",
                 os.path.join("current", "conanfile.txt"): ""})
    client.run("install ./current -pr=./profiles/default")
    assert "os=AIX" in client.out


def test_profile_from_temp_absolute_path():
    """ When passing absolute path as profile file, it MUST be used
        conan install . -pr=/tmp/profiles/default
        /tmp/profiles/default MUST be consumed as target profile
    """
    client = TestClient()
    client.save({"profiles/default": "[settings]\nos=AIX",
                 "current/conanfile.txt": ""})
    profile_path = os.path.join(client.current_folder, "profiles", "default")
    recipe_path = os.path.join(client.current_folder, "current", "conanfile.txt")
    client.run('install "{}" -pr="{}"'.format(recipe_path, profile_path))
    assert "os=AIX" in client.out


def test_consumer_specific_settings():
    client = TestClient()
    dep = str(GenConanfile().with_settings("build_type").with_option("shared", [True, False])
              .with_default_option("shared", False))
    configure = """
    def configure(self):
        self.output.warn("I'm {} and my build type is {}".format(self.name,
                                                                 self.settings.build_type))
        self.output.warn("I'm {} and my shared is {}".format(self.name, self.options.shared))
    """
    dep += configure
    client.save({"conanfile.py": dep})
    client.run("create . dep/1.0@")
    client.run("create . dep/1.0@ -s build_type=Debug -o dep:shared=True")

    consumer = str(GenConanfile().with_settings("build_type").with_requires("dep/1.0")
                   .with_option("shared", [True, False]).with_default_option("shared", False))
    consumer += configure
    client.save({"conanfile.py": consumer})

    # Regular install with release
    client.run("install . -s build_type=Release")
    assert "I'm dep and my build type is Release" in client.out
    assert "I'm None and my build type is Release" in client.out
    assert "I'm dep and my shared is False" in client.out
    assert "I'm None and my shared is False" in client.out

    # Now the dependency by name
    client.run("install . -s dep:build_type=Debug -o dep:shared=True")
    assert "I'm dep and my build type is Debug" in client.out
    assert "I'm None and my build type is Release" in client.out
    assert "I'm dep and my shared is True" in client.out
    assert "I'm None and my shared is False" in client.out

    # Now the consumer using &
    client.run("install . -s &:build_type=Debug -o &:shared=True")
    assert "I'm dep and my build type is Release" in client.out
    assert "I'm None and my build type is Debug" in client.out
    assert "I'm dep and my shared is False" in client.out
    assert "I'm None and my shared is True" in client.out

    # Now use a conanfile.txt
    client.save({"conanfile.txt": textwrap.dedent("""
            [requires]
            dep/1.0
    """)}, clean_first=True)

    # Regular install with release
    client.run("install . -s build_type=Release")
    assert "I'm dep and my build type is Release" in client.out

    # Now the dependency by name
    client.run("install . -s dep:build_type=Debug -o dep:shared=True")
    assert "I'm dep and my build type is Debug" in client.out
    assert "I'm dep and my shared is True" in client.out

    # Test that the generators take the setting
    if platform.system() != "Windows":  # Toolchain in windows is multiconfig
        # Now the consumer using &
        client.run("install . -s &:build_type=Debug -g CMakeToolchain")
        assert "I'm dep and my build type is Release" in client.out
        # Verify the cmake toolchain takes Debug
        assert "I'm dep and my shared is False" in client.out
        presets = json.loads(client.load("CMakePresets.json"))
        assert presets["configurePresets"][0]["cacheVariables"]['CMAKE_BUILD_TYPE'] == "Debug"


def test_create_and_priority_of_consumer_specific_setting():
    client = TestClient()
    conanfile = str(GenConanfile().with_settings("build_type").with_name("foo").with_version("1.0"))
    configure = """
    def configure(self):
        self.output.warn("I'm {} and my build type is {}".format(self.name,
                                                                 self.settings.build_type))
    """
    conanfile += configure
    client.save({"conanfile.py": conanfile})
    client.run("create . -s foo:build_type=Debug")
    assert "I'm foo and my build type is Debug" in client.out

    client.run("create . -s foo:build_type=Debug -s &:build_type=Release")
    assert "I'm foo and my build type is Release" in client.out

    # The order doesn't matter
    client.run("create . -s &:build_type=Release -s foo:build_type=Debug ")
    assert "I'm foo and my build type is Release" in client.out

    # With test_package also works
    test = str(GenConanfile().with_test("pass").with_setting("build_type"))
    test += configure
    client.save({"test_package/conanfile.py": test})
    client.run("create . -s &:build_type=Debug -s build_type=Release")
    assert "I'm foo and my build type is Debug" in client.out
    # the test package recipe has debug too
    assert "I'm None and my build type is Debug" in client.out


def test_consumer_specific_settings_from_profile():
    client = TestClient()
    conanfile = str(GenConanfile().with_settings("build_type").with_name("hello"))
    configure = """
    def configure(self):
        self.output.warn("I'm {} and my build type is {}".format(self.name,
                                                                 self.settings.build_type))
    """
    conanfile += configure
    profile = textwrap.dedent("""
        include(default)
        [settings]
        &:build_type=Debug
    """)
    client.save({"conanfile.py": conanfile, "my_profile.txt": profile})
    client.run("install . --profile my_profile.txt")
    assert "I'm hello and my build type is Debug" in client.out
