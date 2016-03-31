
import unittest
from conans.client.configure_environment import ConfigureEnvironment
from conans.model.settings import Settings
from conans.client.gcc import GCC


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
    def include_paths(self):
        return ["path/to/includes/lib1", "path/to/includes/lib2"]

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

    def configure_environment_test(self):
        env = ConfigureEnvironment(BuildInfoMock(), MockWinSettings())
        self.assertEquals(env.command_line, 'SET LIB="path/to/lib1";"path/to/lib2";%LIB% && '
                                            'SET CL=/I"path/to/includes/lib1" '
                                            '/I"path/to/includes/lib2"')

        env = ConfigureEnvironment(BuildInfoMock(), MockLinuxSettings())
        self.assertEquals(env.command_line, 'env LIBS="-llib1 -llib2" LDFLAGS="-Lpath/to/lib1 '
                                            '-Lpath/to/lib2 -m32" CFLAGS="-m32 cflag1 -s -DNDEBUG" '
                                            'CPPFLAGS="-m32 cppflag1" '
                                            'C_INCLUDE_PATH="path/to/includes/lib1":'
                                            '"path/to/includes/lib2" '
                                            'CPP_INCLUDE_PATH="path/to/includes/lib1":'
                                            '"path/to/includes/lib2"')
        # Not supported yet
        env = ConfigureEnvironment(BuildInfoMock(), MockWinGccSettings())
        self.assertEquals(env.command_line, "")

    def gcc_test(self):
        gcc = GCC(MockLinuxSettings())
        self.assertEquals(gcc.command_line, "-s -DNDEBUG -m32 ")

        gcc = GCC(MockLinuxSettings("Debug"))
        self.assertEquals(gcc.command_line, "-g -m32 ")
