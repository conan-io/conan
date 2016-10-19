
import unittest
from conans.client.configure_environment import ConfigureEnvironment
from conans.model.settings import Settings
from conans.client.gcc import GCC
import platform
import os
from conans.client.runner import ConanRunner
from conans.test.tools import TestBufferConanOutput, TestClient
from conans.test.utils.test_files import temp_folder
from conans.model.profile import Profile
from conans.model.scope import Scopes
from conans.util.files import save
from conans.paths import CONANFILE


class MockWinSettings(Settings):

    @property
    def os(self):
        return "Windows"

    @property
    def arch(self):
        return "x86"

    @property
    def compiler(self):
        class Compiler(object):
            @property
            def version(self):
                return "14"

            def __str__(self):
                return "Visual Studio"
        return Compiler()

    @property
    def build_type(self):
        return "release"


class MockWinGccSettings(MockWinSettings):

    @property
    def compiler(self):
        return "gcc"


class MockLinuxSettings(Settings):

    def __init__(self, build_type="Release"):
        self._build_type = build_type

    @property
    def os(self):
        return "Linux"

    @property
    def arch(self):
        return "x86"

    @property
    def compiler(self):
        return "gcc"

    @property
    def build_type(self):
        return self._build_type


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
    pass


class CompileHelpersTest(unittest.TestCase):

    def setUp(self):
        self.current = os.getcwd()
        os.chdir(temp_folder())

    def tearDown(self):
        os.chdir(self.current)

    def configure_environment_test(self):
        env = ConfigureEnvironment(BuildInfoMock(), MockWinSettings())

        expected = 'call "%vs140comntools%../../VC/vcvarsall.bat" x86 && call _conan_env.bat'
        self.assertEquals(env.command_line, expected)

        env = ConfigureEnvironment(BuildInfoMock(), MockLinuxSettings())
        self.assertEquals(env.command_line, 'env LIBS="-llib1 -llib2" LDFLAGS="-Lpath/to/lib1 '
                                            '-Lpath/to/lib2 -m32 -framework thing -framework thing2 $LDFLAGS" '
                                            'CFLAGS="$CFLAGS -m32 cflag1 -s -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'CPPFLAGS="$CPPFLAGS -m32 cppflag1 -s -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'C_INCLUDE_PATH=$C_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2" '
                                            'CPLUS_INCLUDE_PATH=$CPLUS_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2"')
        # Not supported yet
        env = ConfigureEnvironment(BuildInfoMock(), MockWinGccSettings())
        self.assertEquals(env.command_line_env, 'call _conan_env.bat')

    def gcc_test(self):
        gcc = GCC(MockLinuxSettings())
        self.assertEquals(gcc.command_line, "-s -DNDEBUG -m32 ")

        gcc = GCC(MockLinuxSettings("Debug"))
        self.assertEquals(gcc.command_line, "-g -m32 ")

    def append_variables_test(self):
        output = TestBufferConanOutput()
        runner = ConanRunner()
        if platform.system() != "Windows":
            os.environ["LDFLAGS"] = "ldflag=23 otherldflag=33"
            os.environ["CPPFLAGS"] = "-cppflag -othercppflag"
            os.environ["CFLAGS"] = "-cflag"
            os.environ["C_INCLUDE_PATH"] = "/path/to/c_include_path:/anotherpath"
            os.environ["CPLUS_INCLUDE_PATH"] = "/path/to/cpp_include_path:/anotherpathpp"

            env = ConfigureEnvironment(BuildInfoMock(), MockLinuxSettings())
            runner(env.command_line, output=output)
            self.assertIn("LDFLAGS=-Lpath/to/lib1 -Lpath/to/lib2 -m32 -framework thing -framework thing2 ldflag=23 otherldflag=33\n", output)
            self.assertIn("CPPFLAGS=-cppflag -othercppflag -m32 cppflag1 -s -DNDEBUG -Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2\n", output)
            self.assertIn("CFLAGS=-cflag -m32 cflag1 -s -DNDEBUG -Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2\n", output)
            self.assertIn("C_INCLUDE_PATH=/path/to/c_include_path:/anotherpath:path/to/includes/lib1:path/to/includes/lib2\n", output)
            self.assertIn("CPLUS_INCLUDE_PATH=/path/to/cpp_include_path:/anotherpathpp:path/to/includes/lib1:path/to/includes/lib2\n", output)

            # Reset env vars to not mess with other tests
            os.environ["LDFLAGS"] = ""
            os.environ["CPPFLAGS"] = ""
            os.environ["CFLAGS"] = ""
            os.environ["C_INCLUDE_PATH"] = ""
            os.environ["CPLUS_INCLUDE_PATH"] = ""
        else:
            os.environ["LIB"] = '/path/to/lib.a'
            os.environ["CL"] = '/I"path/to/cl1" /I"path/to/cl2"'

            env = ConfigureEnvironment(BuildInfoMock(), MockWinSettings())
            command = "%s && SET" % env.command_line
            runner(command, output=output)

            self.assertIn('/path/to/lib.a;path/to/lib1;path/to/lib2', output)
            self.assertIn('CL=/I"path/to/cl1" /I"path/to/cl2" '
                          '/I"path/to/includes/lib1" /I"path/to/includes/lib2"', output)

            os.environ["LIB"] = ""
            os.environ["CL"] = ""


conanfile_scope_env = """
from conans import ConanFile, ConfigureEnvironment

class AConan(ConanFile):
    settings = "os"
    requires = "Hello/0.1@lasote/testing"
    generators = "env"

    def build(self):
        env = ConfigureEnvironment(self)
        self.run(env.command_line + (" && SET" if self.settings.os=="Windows" else " && export"))
"""

conanfile_dep = """
from conans import ConanFile

class AConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def package_info(self):
        self.env_info.PATH=["/path/to/my/folder"]
"""


class ConfigureEnvironmentTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def build_with_profile_test(self):
        self._create_profile("scopes_env", {},
                             {},  # undefined scope do not apply to my packages
                             {"CXX": "/path/tomy/g++_build", "CC": "/path/tomy/gcc_build"})

        self.client.save({CONANFILE: conanfile_dep})
        self.client.run("export lasote/testing")

        self.client.save({CONANFILE: conanfile_scope_env}, clean_first=True)
        self.client.run("install --build=missing")
        self.client.run("build -pr scopes_env")
        self.assertRegexpMatches(str(self.client.user_io.out), "PATH=['\"]?/path/to/my/folder")
        self._assert_env_variable_printed("CC", "/path/tomy/gcc_build")
        self._assert_env_variable_printed("CXX", "/path/tomy/g++_build")

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
