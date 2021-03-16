import os
import unittest

import six

from conans.model.profile import Profile
from conans.paths import CONANFILE
from conans.test.utils.tools import  TestClient
from conans.util.files import save


conanfile_scope_env = """
from conans import ConanFile

class AConan(ConanFile):
    settings = "os"
    requires = "Hello/0.1@lasote/testing"

    def build(self):
        self.run("SET" if self.settings.os=="Windows" else "env")
"""

conanfile_dep = """
from conans import ConanFile

class AConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def package_info(self):
        self.env_info.PATH=["/path/to/my/folder"]
"""


class ProfilesEnvironmentTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def test_build_with_profile(self):
        self._create_profile("scopes_env", {},
                             {"CXX": "/path/tomy/g++_build", "CC": "/path/tomy/gcc_build"})

        self.client.save({CONANFILE: conanfile_dep})
        self.client.run("export . lasote/testing")

        self.client.save({CONANFILE: conanfile_scope_env}, clean_first=True)
        self.client.run("install . --build=missing -pr scopes_env")
        self.client.run("build .")
        six.assertRegex(self, str(self.client.out), "PATH=['\"]*/path/to/my/folder")
        self._assert_env_variable_printed("CC", "/path/tomy/gcc_build")
        self._assert_env_variable_printed("CXX", "/path/tomy/g++_build")

    def _assert_env_variable_printed(self, name, value):
        self.assertIn("%s=%s" % (name, value), self.client.out)

    def _create_profile(self, name, settings, env=None):
        env = env or {}
        profile = Profile()
        profile._settings = settings or {}
        for varname, value in env.items():
            profile.env_values.add(varname, value)
        save(os.path.join(self.client.cache.profiles_path, name), "include(default)\n" + profile.dumps())
