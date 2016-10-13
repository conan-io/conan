
import unittest
from conans.client.configure_environment import ConfigureEnvironment
from conans.model.settings import Settings
from conans.client.gcc import GCC
import platform
import os
from conans.client.runner import ConanRunner
from conans.test.tools import TestBufferConanOutput
from conans.test.utils.test_files import temp_folder


class MockWinSettings(Settings):

    @property
    def os(self):
        return "Windows"

    @property
    def arch(self):
        return "x86"

    @property
    def compiler(self):
        return "Visual Studio"

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


class CompileHelpersTest(unittest.TestCase):

    def setUp(self):
        self.current = os.getcwd()
        os.chdir(temp_folder())

    def tearDown(self):
        os.chdir(self.current)

    def configure_environment_test(self):
        env = ConfigureEnvironment(BuildInfoMock(), MockWinSettings())

        expected = ('SET LIB="path/to/lib1";"path/to/lib2";%LIB% && '
                    'SET CL=/I"path/to/includes/lib1" '
                    '/I"path/to/includes/lib2"')

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
            os.environ["LIB"] = '"/path/to/lib.a"'
            os.environ["CL"] = '/I"path/to/cl1" /I"path/to/cl2"'

            env = ConfigureEnvironment(BuildInfoMock(), MockWinSettings())
            command = "%s && SET" % env.command_line
            runner(command, output=output)

            self.assertIn('LIB="path/to/lib1";"path/to/lib2";"/path/to/lib.a"', output)
            self.assertIn('CL=/I"path/to/includes/lib1" /I"path/to/includes/lib2"', output)

            os.environ["LIB"] = ""
            os.environ["CL"] = ""
