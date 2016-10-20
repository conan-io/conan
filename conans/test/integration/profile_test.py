import unittest
from conans.test.tools import TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.profile import Profile
from conans.util.files import save, load
import os
from conans.model.scope import Scopes
import platform
from conans.paths import CONANFILE


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

    def build_with_profile_test(self):
        self._create_profile("scopes_env", {},
                             {},  # undefined scope do not apply to my packages
                             {"CXX": "/path/tomy/g++_build", "CC": "/path/tomy/gcc_build"})

        self.client.save({CONANFILE: conanfile_scope_env})
        self.client.run("build -pr scopes_env")
        self._assert_env_variable_printed("CC", "/path/tomy/gcc_build")
        self._assert_env_variable_printed("CXX", "/path/tomy/g++_build")

    def install_profile_settings_test(self):
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        files["conanfile.py"] = files["conanfile.py"].replace("generators =", "generators = \"txt\",")

        # Create a profile and use it
        profile_settings = {"compiler": "Visual Studio",
                            "compiler.version": "12",
                            "compiler.runtime": "MD",
                            "arch": "x86"}
        self._create_profile("vs_12_86", profile_settings)

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

    def scopes_env_test(self):
        # Create a profile and use it
        self._create_profile("scopes_env", {},
                             {"Hello0:myscope": "1",
                              "ALL:otherscope": "2",
                              "undefined": "3"},  # undefined scope do not apply to my packages
                             {"CXX": "/path/tomy/g++", "CC": "/path/tomy/gcc"})
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
        self._create_profile("scopes_env", {},
                             {},
                             {"ONE_VAR": "ONE_VALUE"})

        self.client.save(files)
        self.client.run("test_package --profile scopes_env")

        self._assert_env_variable_printed("ONE_VAR", "ONE_VALUE")
        self.assertIn("My var is ONE_VALUE", str(self.client.user_io.out))

    def _assert_env_variable_printed(self, name, value):
        if platform.system() == "Windows":
            self.assertIn("%s=%s" % (name, value), self.client.user_io.out)
        elif platform.system() == "Darwin":
            self.assertIn('%s="%s"' % (name, value), self.client.user_io.out)
        else:
            self.assertIn("%s='%s'" % (name, value), self.client.user_io.out)

    def _create_profile(self, name, settings, scopes=None, env=None):
        profile = Profile()
        profile.settings = settings or {}
        if scopes:
            profile.scopes = Scopes.from_list(["%s=%s" % (key, value) for key, value in scopes.items()])
        profile.env = env or {}
        save(self.client.client_cache.profile_path(name), profile.dumps())