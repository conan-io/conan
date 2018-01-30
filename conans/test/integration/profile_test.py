import unittest

from conans.client import tools
from conans.test.utils.tools import TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import save, load
import os
from conans.paths import CONANFILE
from collections import OrderedDict
from conans.test.utils.test_files import temp_folder
from conans.test.utils.profiles import create_profile as _create_profile
from nose_parameterized import parameterized


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

    def base_profile_generated_test(self):
        """we are testing that the default profile is created (when not existing, fresh install)
         even when you run a create with a profile"""
        client = TestClient()
        client.save({CONANFILE: conanfile_scope_env,
                          "myprofile": "include(default)\n[settings]\nbuild_type=Debug"})
        client.run("create . conan/testing --profile myprofile")

    def bad_syntax_test(self):
        self.client.save({CONANFILE: conanfile_scope_env})
        self.client.run("export . lasote/stable")

        profile = '''
        [settings
        '''
        clang_profile_path = os.path.join(self.client.client_cache.profiles_path, "clang")
        save(clang_profile_path, profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang",
                        ignore_error=True)
        self.assertIn("Error reading 'clang' profile", self.client.user_io.out)
        self.assertIn("Bad syntax", self.client.user_io.out)

        profile = '''
        [settings]
        [invented]
        '''
        save(clang_profile_path, profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang",
                        ignore_error=True)
        self.assertIn("Unrecognized field 'invented'", self.client.user_io.out)
        self.assertIn("Error reading 'clang' profile", self.client.user_io.out)

        profile = '''
        [settings]
        as
        '''
        save(clang_profile_path, profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang",
                        ignore_error=True)
        self.assertIn("Error reading 'clang' profile: Invalid setting line 'as'",
                      self.client.user_io.out)

        profile = '''
        [env]
        as
        '''
        save(clang_profile_path, profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang",
                        ignore_error=True)
        self.assertIn("Error reading 'clang' profile: Invalid env line 'as'",
                      self.client.user_io.out)

        profile = '''
        [settings]
        os =   a value
        '''
        save(clang_profile_path, profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang",
                        ignore_error=True)
        # stripped "a value"
        self.assertIn("'a value' is not a valid 'settings.os'", self.client.user_io.out)

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

    @parameterized.expand([("", ), ("./local_profiles/", ), (temp_folder() + "/", )])
    def install_with_missing_profile_test(self, path):
        self.client.save({CONANFILE: conanfile_scope_env})
        error = self.client.run('install . -pr "%sscopes_env"' % path, ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Profile not found:", self.client.out)
        self.assertIn("scopes_env", self.client.out)

    def install_profile_env_test(self):
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        files["conanfile.py"] = conanfile_scope_env

        create_profile(self.client.client_cache.profiles_path, "envs", settings={},
                       env=[("A_VAR", "A_VALUE")], package_env={"Hello0": [("OTHER_VAR", "2")]})

        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr envs")
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

    def install_profile_settings_test(self):
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)

        # Create a profile and use it
        profile_settings = OrderedDict([("compiler", "Visual Studio"),
                                        ("compiler.version", "12"),
                                        ("compiler.runtime", "MD"),
                                        ("arch", "x86")])

        create_profile(self.client.client_cache.profiles_path, "vs_12_86",
                       settings=profile_settings, package_settings={})

        self.client.client_cache.default_profile # Creates default
        tools.replace_in_file(self.client.client_cache.default_profile_path,
                              "compiler.libcxx", "#compiler.libcxx", strict=False)

        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.client.run("install . --build missing -pr vs_12_86")
        info = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        for setting, value in profile_settings.items():
            self.assertIn("%s=%s" % (setting, value), info)

        # Try to override some settings in install command
        self.client.run("install . --build missing -pr vs_12_86 -s compiler.version=14")
        info = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
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
        create_profile(self.client.client_cache.profiles_path,
                       "vs_12_86_Hello0_gcc", settings=profile_settings,
                       package_settings=package_settings)
        # Try to override some settings in install command
        self.client.run("install . --build missing -pr vs_12_86_Hello0_gcc -s compiler.version=14")
        info = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("compiler=gcc", info)
        self.assertIn("compiler.libcxx=libstdc++11", info)

        # If other package is specified compiler is not modified
        package_settings = {"NoExistsRecipe": tmp_settings}
        create_profile(self.client.client_cache.profiles_path,
                       "vs_12_86_Hello0_gcc", settings=profile_settings,
                       package_settings=package_settings)
        # Try to override some settings in install command
        self.client.run("install . --build missing -pr vs_12_86_Hello0_gcc -s compiler.version=14")
        info = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("compiler=Visual Studio", info)
        self.assertNotIn("compiler.libcxx", info)

        # Mix command line package settings with profile
        package_settings = {"Hello0": tmp_settings}
        create_profile(self.client.client_cache.profiles_path, "vs_12_86_Hello0_gcc",
                       settings=profile_settings, package_settings=package_settings)

        # Try to override some settings in install command
        self.client.run("install . --build missing -pr vs_12_86_Hello0_gcc"
                        " -s compiler.version=14 -s Hello0:compiler.libcxx=libstdc++")
        info = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("compiler=gcc", info)
        self.assertNotIn("compiler.libcxx=libstdc++11", info)
        self.assertIn("compiler.libcxx=libstdc++", info)

    def install_profile_options_test(self):
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)

        create_profile(self.client.client_cache.profiles_path, "vs_12_86",
                       options=[("Hello0:language", 1),
                                ("Hello0:static", False)])

        self.client.save(files)
        self.client.run("install . --build missing -pr vs_12_86")
        info = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("language=1", info)
        self.assertIn("static=False", info)

    def scopes_env_test(self):
        # Create a profile and use it
        create_profile(self.client.client_cache.profiles_path, "scopes_env", settings={},
                       env=[("CXX", "/path/tomy/g++"), ("CC", "/path/tomy/gcc")])
        self.client.save({CONANFILE: conanfile_scope_env})
        self.client.run("export . lasote/stable")
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr scopes_env")

        self._assert_env_variable_printed("CC", "/path/tomy/gcc")
        self._assert_env_variable_printed("CXX", "/path/tomy/g++")

        # The env variable shouldn't persist after install command
        self.assertFalse(os.environ.get("CC", None) == "/path/tomy/gcc")
        self.assertFalse(os.environ.get("CXX", None) == "/path/tomy/g++")

    def default_including_another_profile_test(self):
        p1 = "include(p2)\n[env]\nA_VAR=1"
        p2 = "include(default)\n[env]\nA_VAR=2"
        self.client.client_cache.conan_config  # Create the default conf
        self.client.client_cache.default_profile  # Create default profile
        save(os.path.join(self.client.client_cache.profiles_path, "p1"), p1)
        save(os.path.join(self.client.client_cache.profiles_path, "p2"), p2)
        # Change default profile to p1 => p2 => default
        tools.replace_in_file(self.client.client_cache.conan_conf_path,
                              "default_profile = default",
                              "default_profile = p1")
        self.client.save({CONANFILE: conanfile_scope_env})
        self.client.run("create . user/testing")
        self._assert_env_variable_printed("A_VAR", "1")

    def test_package_test(self):
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
        create_profile(self.client.client_cache.profiles_path, "scopes_env", settings={},
                       env=[("ONE_VAR", "ONE_VALUE")])

        self.client.save(files)
        self.client.run("create . lasote/stable --profile scopes_env")

        self._assert_env_variable_printed("ONE_VAR", "ONE_VALUE")
        self.assertIn("My var is ONE_VALUE", str(self.client.user_io.out))

        # Try now with package environment vars
        create_profile(self.client.client_cache.profiles_path, "scopes_env2", settings={},
                       package_env={"DefaultName": [("ONE_VAR", "IN_TEST_PACKAGE")],
                                    "Hello0": [("ONE_VAR", "PACKAGE VALUE")]})

        self.client.run("create . lasote/stable --profile scopes_env2")

        self._assert_env_variable_printed("ONE_VAR", "PACKAGE VALUE")
        self.assertIn("My var is IN_TEST_PACKAGE", str(self.client.user_io.out))

        # Try now overriding some variables with command line
        self.client.run("create . lasote/stable --profile scopes_env2 "
                        "-e DefaultName:ONE_VAR=InTestPackageOverride "
                        "-e Hello0:ONE_VAR=PackageValueOverride ")

        self._assert_env_variable_printed("ONE_VAR", "PackageValueOverride")
        self.assertIn("My var is InTestPackageOverride", str(self.client.user_io.out))

        # A global setting in command line won't override a scoped package variable
        self.client.run("create . lasote/stable --profile scopes_env2 -e ONE_VAR=AnotherValue")
        self._assert_env_variable_printed("ONE_VAR", "PACKAGE VALUE")

    def _assert_env_variable_printed(self, name, value):
        self.assertIn("%s=%s" % (name, value), self.client.user_io.out)

    def info_with_profiles_test(self):

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
        create_profile(self.client.client_cache.profiles_path, "scopes_env",
                       settings={"os": "Linux"})

        # Install with the previous profile
        self.client.run("info Hello/0.1@lasote/stable --profile scopes_env")
        self.assertNotIn('''Requires:
                WinRequire/0.1@lasote/stable''', self.client.user_io.out)

        # Create a profile that activate the require
        create_profile(self.client.client_cache.profiles_path, "scopes_env",
                       settings={"os": "Windows"})

        # Install with the previous profile
        self.client.run("info Hello/0.1@lasote/stable --profile scopes_env")
        self.assertIn('''Requires:
        WinRequire/0.1@lasote/stable''', self.client.user_io.out)
