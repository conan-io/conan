import unittest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient

"""

DEPENDENCY GRAPH:
-----------------

MyLib -> MyLibParent
MyLib2


BUILD DEPENDENCY GRAPH:
----------------------

BuildRequire -> BuildRequireParent (Applied both for Mylib and Mylib2 because is global)
BuildRequire2 (Applied only to MyLib2)
"""


build_require_parent = """
import os
from conans import ConanFile

def assert_msg(lhs, rhs):
    assert lhs == rhs, "{} != {}".format(lhs, rhs)

class BuildRequireParent(ConanFile):
    name = "BuildRequireParent"
    version = "0.1"
    settings = "os", "compiler", "arch"

    def build(self):
        # Assert settings inherited from profile
        assert_msg(self.settings.os, "Windows")
        assert_msg(self.settings.compiler, "gcc")
        assert_msg(os.environ["PROFILE_VAR_ENV"], "PROFILE_VAR_VALUE_BUILD")
        assert_msg(os.environ["ENV_VAR_ONLY_PARENT"], "1_BUILD")

    def package_info(self):
        self.cpp_info.cflags.append("A_C_FLAG_FROM_BUILD_REQUIRE_PARENT")
        self.env_info.ENV_VAR = "ENV_VALUE_FROM_BUILD_REQUIRE_PARENT"
        self.env_info.ENV_VAR_MULTI.append("ENV_VALUE_MULTI_FROM_BUILD_REQUIRE_PARENT")
        self.cpp_info.sysroot = "path/to/folder"
"""

build_require = """
import os
from conans import ConanFile

def assert_msg(lhs, rhs):
    assert lhs == rhs, "{} != {}".format(lhs, rhs)
    
class BuildRequire(ConanFile):
    name = "BuildRequire"
    version = "0.1"
    settings = "os", "compiler", "arch"
    requires = "BuildRequireParent/0.1@lasote/stable"
    options = {"activate_foo": [True, False]}
    default_options = "activate_foo=False"

    def build(self):
        assert_msg(self.settings.os, "Windows")
        assert_msg(self.settings.compiler, "gcc")
        assert_msg(os.environ["ENV_VAR"], "ENV_VALUE_FROM_BUILD_REQUIRE_PARENT")
        assert_msg(os.environ["ENV_VAR_MULTI"], "ENV_VALUE_MULTI_FROM_BUILD_REQUIRE_PARENT")
        assert_msg(os.environ["PROFILE_VAR_ENV"], "PROFILE_VAR_VALUE_BUILD")
        assert_msg(os.environ["ENV_VAR_ONLY_PARENT"], "0_BUILD")

    def package_info(self):
        self.cpp_info.cflags.append("A_C_FLAG_FROM_BUILD_REQUIRE")
        self.env_info.ENV_VAR = "ENV_VALUE_FROM_BUILD_REQUIRE"
        self.env_info.ENV_VAR_MULTI.append("ENV_VALUE_MULTI_FROM_BUILD_REQUIRE")
        if self.options.activate_foo:
            self.env_info.FOO_VAR = "1"
        else:
            self.env_info.FOO_VAR = "0"

"""

build_require2 = """
import os
from conans import ConanFile

def assert_msg(lhs, rhs):
    assert lhs == rhs, "{} != {}".format(lhs, rhs)
    
class BuildRequire2(ConanFile):
    name = "BuildRequire2"
    version = "0.1"
    settings = "os", "compiler", "arch"

    def build(self):
        assert_msg(self.settings.os, "Windows")
        assert_msg(self.settings.compiler, "gcc")
        assert_msg(os.environ["PROFILE_VAR_ENV"], "PROFILE_VAR_VALUE_BUILD")

    def package_info(self):
        self.cpp_info.cflags.append("A_C_FLAG_FROM_BUILD_REQUIRE2")
        self.env_info.ENV_VAR_REQ2 = "ENV_VALUE_FROM_BUILD_REQUIRE2"
        self.env_info.ENV_VAR_MULTI.append("ENV_VALUE_MULTI_FROM_BUILD_REQUIRE2")
        self.cpp_info.sysroot = "path/to/other_folder"

"""

my_lib_parent = """
import os
from conans import ConanFile

def assert_msg(lhs, rhs):
    assert lhs == rhs, "{} != {}".format(lhs, rhs)
    
class MyLibParent(ConanFile):
    name = "MyLibParent"
    version = "0.1"
    settings = "os", "compiler", "arch"

    def build(self):
        # only from BuildRequire
        assert_msg(os.environ["PROFILE_VAR_ENV"], "PROFILE_VAR_VALUE_HOST")
        assert_msg(os.environ.get("ENV_VAR", None), "ENV_VALUE_FROM_BUILD_REQUIRE")
        assert_msg(os.environ.get("ENV_VAR_MULTI", None), "ENV_VALUE_MULTI_FROM_BUILD_REQUIRE" + os.pathsep + "ENV_VALUE_MULTI_FROM_BUILD_REQUIRE_PARENT")
        assert_msg(os.environ.get("ENV_VAR_REQ2", None), None)

    def package_info(self):
        self.cpp_info.cflags.append("A_C_FLAG_FROM_MYLIB_PARENT")
        self.env_info.ENV_VAR_MULTI.append("ENV_VALUE_MULTI_FROM_MYLIB_PARENT")

"""

my_lib = """
import os
from conans import ConanFile

def assert_msg(lhs, rhs):
    assert lhs == rhs, "{} != {}".format(lhs, rhs)

class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"
    settings = "os", "compiler", "arch"
    requires = "MyLibParent/0.1@lasote/stable"
    generators = "cmake"

    def config_options(self):
        assert_msg(os.environ["PROFILE_VAR_ENV"], "PROFILE_VAR_VALUE_HOST")

    def requirements(self):
        assert_msg(os.environ["PROFILE_VAR_ENV"], "PROFILE_VAR_VALUE_HOST")

    def build(self):
        # only from BuildRequire
        assert_msg(os.environ["PROFILE_VAR_ENV"], "PROFILE_VAR_VALUE_HOST")
        assert_msg(os.environ["ENV_VAR_ONLY_PARENT"], "0_HOST")
        assert_msg(os.environ["ENV_VAR"], "ENV_VALUE_FROM_BUILD_REQUIRE")
        assert_msg(os.environ.get("ENV_VAR_REQ2", None), None)
        
        tmp = os.pathsep.join(["ENV_VALUE_MULTI_FROM_BUILD_REQUIRE",
                               "ENV_VALUE_MULTI_FROM_MYLIB_PARENT",
                               "ENV_VALUE_MULTI_FROM_BUILD_REQUIRE_PARENT"])
        assert_msg(os.environ["ENV_VAR_MULTI"], tmp)

        assert_msg(self.deps_cpp_info.cflags, ["A_C_FLAG_FROM_BUILD_REQUIRE_PARENT",
                                               "A_C_FLAG_FROM_MYLIB_PARENT",
                                               "A_C_FLAG_FROM_BUILD_REQUIRE"])
        assert_msg(self.deps_cpp_info.sysroot, "path/to/folder")
        assert_msg(os.environ["FOO_VAR"], "1")
"""


my_lib2 = """
import os
from conans import ConanFile

def assert_msg(lhs, rhs):
    assert lhs == rhs, "{} != {}".format(lhs, rhs)
    
class MyLib2(ConanFile):
    name = "MyLib2"
    version = "0.1"
    settings = "os", "compiler", "arch"

    def build(self):
        # From BuildRequire and BuildRequire2
        assert_msg(os.environ["PROFILE_VAR_ENV"], "PROFILE_VAR_VALUE_HOST")
        assert_msg(os.environ["ENV_VAR_ONLY_PARENT"], "0_HOST")
        assert_msg(os.environ["ENV_VAR"], "ENV_VALUE_FROM_BUILD_REQUIRE")
        assert_msg(os.environ["ENV_VAR_REQ2"], "ENV_VALUE_FROM_BUILD_REQUIRE2")
        
        tmp = os.pathsep.join(["ENV_VALUE_MULTI_FROM_BUILD_REQUIRE",
                               "ENV_VALUE_MULTI_FROM_BUILD_REQUIRE2",
                               "ENV_VALUE_MULTI_FROM_BUILD_REQUIRE_PARENT"])
        assert_msg(os.environ.get("ENV_VAR_MULTI", None), tmp)

        assert_msg(self.deps_cpp_info.cflags, ["A_C_FLAG_FROM_BUILD_REQUIRE_PARENT",
                                               "A_C_FLAG_FROM_BUILD_REQUIRE2",
                                               "A_C_FLAG_FROM_BUILD_REQUIRE"])
        assert_msg(os.environ["FOO_VAR"], "1")
        # Applied in order, so it takes the first value from BuildRequire
        # FIXME assert_msg(self.deps_cpp_info.sysroot, "path/to/other/folder")
"""


profile_host = """
[build_requires]
*: BuildRequire/0.1@lasote/stable
MyLib2/*: BuildRequire2/0.1@lasote/stable

[settings]
os=Windows
compiler=gcc
compiler.version=4.8
compiler.libcxx=libstdc++
arch=x86

[env]
PROFILE_VAR_ENV=PROFILE_VAR_VALUE_HOST
ENV_VAR_ONLY_PARENT=0_HOST
"""

profile_build = """
[settings]
os=Windows
compiler=gcc
compiler.version=4.8
compiler.libcxx=libstdc++
arch=x86

[env]
PROFILE_VAR_ENV=PROFILE_VAR_VALUE_BUILD
BuildRequireParent:ENV_VAR_ONLY_PARENT=1_BUILD
ENV_VAR_ONLY_PARENT=0_BUILD

[options]
BuildRequire:activate_foo=True
"""


class ProfileRequiresTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def _export(self, var_conanfile):
        self.client.save({CONANFILE: var_conanfile}, clean_first=True)
        self.client.run("export . lasote/stable")

    def test_profile_requires(self):
        self._export(build_require_parent)
        self._export(build_require)
        self._export(build_require2)
        self._export(my_lib_parent)
        self._export(my_lib)
        self._export(my_lib2)

        reuse = """
[requires]
MyLib/0.1@lasote/stable
MyLib2/0.1@lasote/stable
[generators]
cmake
gcc
"""
        self.client.save({"profile_host.txt": profile_host,
                          "profile_build.txt": profile_build,
                          "conanfile.txt": reuse}, clean_first=True)
        self.client.run("install . --build missing"
                        " --profile:host ./profile_host.txt"
                        " --profile:build ./profile_build.txt")
