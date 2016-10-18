import unittest
from conans.test.tools import TestServer, TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.profile import Profile
from conans.util.files import save, load
import os
from conans.model.scope import Scopes
import platform


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
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

    def build_with_profile_test(self):
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        files["conanfile.py"] = conanfile_scope_env

        self._create_profile("scopes_env", {},
                             {},  # undefined scope do not apply to my packages
                             {"CXX": "/path/tomy/g++_build", "CC": "/path/tomy/gcc_build"})

        self.client.save(files)
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
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        files["conanfile.py"] = conanfile_scope_env

        # Create a profile and use it
        self._create_profile("scopes_env", {},
                             {"Hello0:myscope": "1",
                              "ALL:otherscope": "2",
                              "undefined": "3"},  # undefined scope do not apply to my packages
                             {"CXX": "/path/tomy/g++", "CC": "/path/tomy/gcc"})
        self.client.save(files)
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
