import os
import unittest

from conans.model.env_info import DepsEnvInfo
from conans.model.profile import Profile
from conans.model.settings import Settings
from conans.paths import CONANFILE
from conans.test.utils.tools import TestBufferConanOutput, TestClient
from conans.util.files import save


class MockSetting(str):
    @property
    def value(self):
        return self


class MockCompiler(object):

    def __init__(self, name, libcxx, version):
        self.name = name
        self.libcxx = libcxx
        self.version = MockSetting(version)

    def __repr__(self, *args, **kwargs):  # @UnusedVariable
        return self.name


class MockSettings(Settings):

    def __init__(self, build_type="Release", os=None, arch=None,
                 compiler_name=None, libcxx=None, version=None):
        self._build_type = build_type
        self._libcxx = libcxx or "libstdc++"
        self._os = os or "Linux"
        self._arch = arch or "x86"
        self._compiler = MockCompiler(compiler_name or "gcc", self._libcxx, version or "4.8")

    @property
    def build_type(self):
        return self._build_type

    @property
    def libcxx(self):
        return self._libcxx

    @property
    def os(self):
        return MockSetting(self._os)

    @property
    def arch(self):
        return MockSetting(self._arch)

    @property
    def compiler(self):
        return self._compiler


class MockAndroidSettings(Settings):

    @property
    def os(self):
        return "Android"


class BuildInfoMock(object):

    @property
    def lib_paths(self):
        return ["path/to/lib1", "path/to/lib2"]

    @property
    def exelinkflags(self):
        return ["-framework thing"]

    @property
    def sharedlinkflags(self):
        return ["-framework thing2"]

    @property
    def include_paths(self):
        return ["path/to/includes/lib1", "path/to/includes/lib2"]

    @property
    def defines(self):
        return ["MYDEF1", "MYDEF2"]

    @property
    def libs(self):
        return ["lib1", "lib2"]

    @property
    def cflags(self):
        return ["cflag1"]

    @property
    def cppflags(self):
        return ["cppflag1"]


class MockConanfile(object):

    def __init__(self, settings):
        self.settings = settings
        self.output = TestBufferConanOutput()

    @property
    def deps_cpp_info(self):
        return BuildInfoMock()

    @property
    def deps_env_info(self):
        return DepsEnvInfo()

    @property
    def env_values_dicts(self):
        return {}, {}


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

    def build_with_profile_test(self):
        self._create_profile("scopes_env", {},
                             {"CXX": "/path/tomy/g++_build", "CC": "/path/tomy/gcc_build"})

        self.client.save({CONANFILE: conanfile_dep})
        self.client.run("export . lasote/testing")

        self.client.save({CONANFILE: conanfile_scope_env}, clean_first=True)
        self.client.run("install . --build=missing --pr scopes_env")
        self.client.run("build .")
        self.assertRegexpMatches(str(self.client.user_io.out), "PATH=['\"]*/path/to/my/folder")
        self._assert_env_variable_printed("CC", "/path/tomy/gcc_build")
        self._assert_env_variable_printed("CXX", "/path/tomy/g++_build")

    def _assert_env_variable_printed(self, name, value):
        self.assertIn("%s=%s" % (name, value), self.client.user_io.out)

    def _create_profile(self, name, settings, env=None):
        env = env or {}
        profile = Profile()
        profile._settings = settings or {}
        for varname, value in env.items():
            profile.env_values.add(varname, value)
        save(os.path.join(self.client.client_cache.profiles_path, name), "include(default)\n" + profile.dumps())
