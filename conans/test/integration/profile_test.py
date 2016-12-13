import unittest
from conans.test.tools import TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import save, load
import os
import platform
from conans.paths import CONANFILE
from collections import OrderedDict
from conans.test.utils.test_files import temp_folder
from conans.test.utils.profiles import create_profile
from nose_parameterized import parameterized


conanfile_scope_env = """
import platform
from conans import ConanFile

class AConan(ConanFile):
    name = "Hello0"
    version = "0.1"
    settings = "os", "compiler", "arch"

    def build(self):
        self.output.warn("Scope myscope: %s" % self.scope.myscope)
        self.output.warn("Scope otherscope: %s" % self.scope.otherscope)
        self.output.warn("Scope undefined: %s" % self.scope.undefined)
        # Print environment vars
        if self.settings.os == "Windows":
            self.run("SET")
        else:
            self.run("export")

"""


class ProfileTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def bad_syntax_test(self):
        self.client.save({CONANFILE: conanfile_scope_env})
        self.client.run("export lasote/stable")

        profile = '''
        [settings
        '''
        save(self.client.client_cache.profile_path("clang"), profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang", ignore_error=True)
        self.assertIn("Error reading 'clang' profile", self.client.user_io.out)
        self.assertIn("Bad syntax", self.client.user_io.out)

        profile = '''
        [settings]
        [invented]
        '''
        save(self.client.client_cache.profile_path("clang"), profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang", ignore_error=True)
        self.assertIn("Unrecognized field 'invented'", self.client.user_io.out)
        self.assertIn("Error reading 'clang' profile", self.client.user_io.out)

        profile = '''
        [settings]
        as
        '''
        save(self.client.client_cache.profile_path("clang"), profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang", ignore_error=True)
        self.assertIn("Error reading 'clang' profile: Invalid setting line 'as'", self.client.user_io.out)

        profile = '''
        [env]
        as
        '''
        save(self.client.client_cache.profile_path("clang"), profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang", ignore_error=True)
        self.assertIn("Error reading 'clang' profile: Invalid env line 'as'", self.client.user_io.out)

        profile = '''
        [scopes]
        as
        '''
        save(self.client.client_cache.profile_path("clang"), profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang", ignore_error=True)
        self.assertIn("Error reading 'clang' profile: Bad scope as", self.client.user_io.out)

        profile = '''
        [settings]
        os =   a value
        '''
        save(self.client.client_cache.profile_path("clang"), profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang", ignore_error=True)
        # stripped "a value"
        self.assertIn("'a value' is not a valid 'settings.os'", self.client.user_io.out)

        profile = '''
        [env]
        ENV_VAR =   a value
        '''
        save(self.client.client_cache.profile_path("clang"), profile)
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr clang", ignore_error=True)
        self._assert_env_variable_printed("ENV_VAR", "a value")

        profile = '''
        # Line with comments is not a problem
        [env]
        # Not even here
        ENV_VAR =   a value
        '''
        save(self.client.client_cache.profile_path("clang"), profile)
        self.client.run("install Hello0/0.1@lasote/stable --build -pr clang", ignore_error=True)
        self._assert_env_variable_printed("ENV_VAR", "a value")

    @parameterized.expand([("", ), ("./local_profiles/", ), (temp_folder() + "/", )])
    def build_with_profile_test(self, path):
        if path == "":
            folder = self.client.client_cache.profiles_path
        elif path == "./local_profiles/":
            folder = os.path.join(self.client.current_folder, "local_profiles")
        else:
            folder = path
        create_profile(folder, "scopes_env", settings={},
                       scopes={},  # undefined scope do not apply to my packages
                       env=[("CXX", "/path/tomy/g++_build"),
                            ("CC", "/path/tomy/gcc_build")])

        self.client.save({CONANFILE: conanfile_scope_env})
        self.client.run('build -pr "%sscopes_env"' % path)
        self._assert_env_variable_printed("CC", "/path/tomy/gcc_build")
        self._assert_env_variable_printed("CXX", "/path/tomy/g++_build")

    @parameterized.expand([("", ), ("./local_profiles/", ), (temp_folder() + "/", )])
    def build_with_missing_profile_test(self, path):
        self.client.save({CONANFILE: conanfile_scope_env})
        error = self.client.run('build -pr "%sscopes_env"' % path, ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Specified profile '%sscopes_env' doesn't exist" % path,
                      self.client.user_io.out)

    def install_profile_env_test(self):
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        files["conanfile.py"] = conanfile_scope_env

        create_profile(self.client.client_cache.profiles_path, "envs", settings={},
                       env=[("A_VAR", "A_VALUE")], package_env={"Hello0": [("OTHER_VAR", 2)]})

        self.client.save(files)
        self.client.run("export lasote/stable")
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr envs")
        self._assert_env_variable_printed("A_VAR", "A_VALUE")
        self._assert_env_variable_printed("OTHER_VAR", "2")

        # Override with package var
        self.client.run("install Hello0/0.1@lasote/stable --build -pr envs -e Hello0:A_VAR=OTHER_VALUE")
        self._assert_env_variable_printed("A_VAR", "OTHER_VALUE")
        self._assert_env_variable_printed("OTHER_VAR", "2")

        # Override package var with package var
        self.client.run("install Hello0/0.1@lasote/stable --build -pr envs -e Hello0:A_VAR=OTHER_VALUE -e Hello0:OTHER_VAR=3")
        self._assert_env_variable_printed("A_VAR", "OTHER_VALUE")
        self._assert_env_variable_printed("OTHER_VAR", "3")

    def install_profile_settings_test(self):
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        files["conanfile.py"] = files["conanfile.py"].replace("generators =", "generators = \"txt\",")

        # Create a profile and use it
        profile_settings = {"compiler": "Visual Studio",
                            "compiler.version": "12",
                            "compiler.runtime": "MD",
                            "arch": "x86"}

        create_profile(self.client.client_cache.profiles_path, "vs_12_86",
                       settings=profile_settings, package_settings={})

        self.client.save(files)
        self.client.run("export lasote/stable")
        self.client.run("install --build missing -pr vs_12_86")
        info = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        for setting, value in profile_settings.items():
            self.assertIn("%s=%s" % (setting, value), info)

        # Try to override some settings in install command
        self.client.run("install --build missing -pr vs_12_86 -s compiler.version=14")
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
        self.client.run("install --build missing -pr vs_12_86_Hello0_gcc -s compiler.version=14")
        info = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("compiler=gcc", info)
        self.assertIn("compiler.libcxx=libstdc++11", info)

        # If other package is specified compiler is not modified
        package_settings = {"NoExistsRecipe": tmp_settings}
        create_profile(self.client.client_cache.profiles_path,
                       "vs_12_86_Hello0_gcc", settings=profile_settings,
                       package_settings=package_settings)
        # Try to override some settings in install command
        self.client.run("install --build missing -pr vs_12_86_Hello0_gcc -s compiler.version=14")
        info = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("compiler=Visual Studio", info)
        self.assertNotIn("compiler.libcxx", info)

        # Mix command line package settings with profile
        package_settings = {"Hello0": tmp_settings}
        create_profile(self.client.client_cache.profiles_path, "vs_12_86_Hello0_gcc",
                       settings=profile_settings, package_settings=package_settings)

        # Try to override some settings in install command
        self.client.run("install --build missing -pr vs_12_86_Hello0_gcc"
                        " -s compiler.version=14 -s Hello0:compiler.libcxx=libstdc++")
        info = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        self.assertIn("compiler=gcc", info)
        self.assertNotIn("compiler.libcxx=libstdc++11", info)
        self.assertIn("compiler.libcxx=libstdc++", info)

    def scopes_env_test(self):
        # Create a profile and use it
        create_profile(self.client.client_cache.profiles_path, "scopes_env", settings={},
                       scopes={"Hello0:myscope": "1",
                               "ALL:otherscope": "2",
                               "undefined": "3"},  # undefined scope do not apply to my packages
                       env=[("CXX", "/path/tomy/g++"), ("CC", "/path/tomy/gcc")])
        self.client.save({CONANFILE: conanfile_scope_env})
        self.client.run("export lasote/stable")
        self.client.run("install Hello0/0.1@lasote/stable --build missing -pr scopes_env")

        self.assertIn("Scope myscope: 1", self.client.user_io.out)
        self.assertIn("Scope otherscope: 2", self.client.user_io.out)
        self.assertIn("Scope undefined: None", self.client.user_io.out)

        self._assert_env_variable_printed("CC", "/path/tomy/gcc")
        self._assert_env_variable_printed("CXX", "/path/tomy/g++")

        # The env variable shouldn't persist after install command
        self.assertFalse(os.environ.get("CC", None) == "/path/tomy/gcc")
        self.assertFalse(os.environ.get("CXX", None) == "/path/tomy/g++")

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
        # self.run('cmake %s %s' % (self.conanfile_directory, cmake.command_line))
        if self.settings.os == "Windows":
            self.run('echo "My var is %ONE_VAR%"')
        else:
            self.run('echo "My var is $ONE_VAR"')

    def test(self):
        pass

'''
        files = {}
        files["conanfile.py"] = conanfile_scope_env
        files["test_package/conanfile.py"] = test_conanfile
        # Create a profile and use it
        create_profile(self.client.client_cache.profiles_path, "scopes_env", settings={},
                       scopes={}, env=[("ONE_VAR", "ONE_VALUE")])

        self.client.save(files)
        self.client.run("test_package --profile scopes_env")

        self._assert_env_variable_printed("ONE_VAR", "ONE_VALUE")
        self.assertIn("My var is ONE_VALUE", str(self.client.user_io.out))

        # Try now with package environment vars
        create_profile(self.client.client_cache.profiles_path, "scopes_env2", settings={},
                       scopes={}, package_env={"DefaultName": [("ONE_VAR", "IN_TEST_PACKAGE")],
                                               "Hello0": [("ONE_VAR", "PACKAGE VALUE")]})

        self.client.run("test_package --profile scopes_env2")

        self._assert_env_variable_printed("ONE_VAR", "PACKAGE VALUE")
        self.assertIn("My var is IN_TEST_PACKAGE", str(self.client.user_io.out))

        # Try now overriding some variables with command line
        self.client.run("test_package --profile scopes_env2 -e DefaultName:ONE_VAR=InTestPackageOverride "
                        "-e Hello0:ONE_VAR=PackageValueOverride ")

        self._assert_env_variable_printed("ONE_VAR", "PackageValueOverride")
        self.assertIn("My var is InTestPackageOverride", str(self.client.user_io.out))

        # A global setting in command line won't override a scoped package variable
        self.client.run("test_package --profile scopes_env2 -e ONE_VAR=AnotherValue")
        self._assert_env_variable_printed("ONE_VAR", "PACKAGE VALUE")

    def _assert_env_variable_printed(self, name, value):
        if platform.system() == "Windows":
            self.assertIn("%s=%s" % (name, value), self.client.user_io.out)
        elif platform.system() == "Darwin":
            self.assertIn('%s="%s"' % (name, value), self.client.user_io.out)
        else:
            self.assertIn("%s='%s'" % (name, value), self.client.user_io.out)
