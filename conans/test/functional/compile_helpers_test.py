import os
import platform
import unittest

from conans.client.configure_environment import ConfigureEnvironment
from conans.client.gcc import GCC
from conans.client.runner import ConanRunner
from conans.errors import ConanException
from conans.model.env_info import DepsEnvInfo
from conans.model.profile import Profile
from conans.model.scope import Scopes
from conans.model.settings import Settings
from conans.paths import CONANFILE
from conans.test.utils.tools import TestBufferConanOutput, TestClient
from conans.test.utils.test_files import temp_folder
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
        return self._os

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


class CompileHelpersTest(unittest.TestCase):

    def setUp(self):
        self.current = os.getcwd()
        os.chdir(temp_folder())

    def tearDown(self):
        os.chdir(self.current)

    def compile_flag_test(self):
        win_settings = MockSettings("Release", os="Windows", arch="x86",
                                    compiler_name="Visual Studio", libcxx=None, version="14")
        env = ConfigureEnvironment(MockConanfile(win_settings))
        self.assertEquals(env.compile_flags, "lib1.lib lib2.lib")

        linux_s = MockSettings("Release", os="Linux", arch="x86",
                               compiler_name="gcc", libcxx="libstdc++", version="4.9")
        env = ConfigureEnvironment(MockConanfile(linux_s))
        self.assertEquals(env.compile_flags, '-m32 -framework thing -framework '
                                             'thing2 -s -DNDEBUG -DMYDEF1 -DMYDEF2 '
                                             '-I"path/to/includes/lib1" -I"path/to/includes/lib2" '
                                             '-L"path/to/lib1" -L"path/to/lib2" -llib1 -llib2 cppflag1 '
                                             '-D_GLIBCXX_USE_CXX11_ABI=0')

        linux_s_11 = MockSettings("Debug", os="Linux", arch="x86_64",
                                  compiler_name="gcc", libcxx="libstdc++11", version="4.9")
        env = ConfigureEnvironment(MockConanfile(linux_s_11))
        self.assertEquals(env.compile_flags, '-m64 -framework thing -framework thing2'
                                             ' -g -DMYDEF1 -DMYDEF2 -I"path/to/includes/lib1" '
                                             '-I"path/to/includes/lib2" -L"path/to/lib1" '
                                             '-L"path/to/lib2" -llib1 -llib2 cppflag1 '
                                             '-D_GLIBCXX_USE_CXX11_ABI=1')

        linux_s_clang_std = MockSettings("Debug", os="Linux", arch="x86_64",
                                         compiler_name="clang", libcxx="libstdc", version="4.9")
        env = ConfigureEnvironment(MockConanfile(linux_s_clang_std))
        self.assertEquals(env.compile_flags, '-m64 -framework thing -framework thing2'
                                             ' -g -DMYDEF1 -DMYDEF2 -I"path/to/includes/lib1" '
                                             '-I"path/to/includes/lib2" -L"path/to/lib1" '
                                             '-L"path/to/lib2" -llib1 -llib2 cppflag1 '
                                             '-stdlib=libstdc++')

        linux_s_clang = MockSettings("Debug", os="Linux", arch="x86_64",
                                     compiler_name="clang", libcxx="libc++", version="4.9")
        env = ConfigureEnvironment(MockConanfile(linux_s_clang))
        self.assertEquals(env.compile_flags, '-m64 -framework thing -framework thing2'
                                             ' -g -DMYDEF1 -DMYDEF2 -I"path/to/includes/lib1" '
                                             '-I"path/to/includes/lib2" -L"path/to/lib1" '
                                             '-L"path/to/lib2" -llib1 -llib2 cppflag1 '
                                             '-stdlib=libc++')

        freebsd_s_clang_32 = MockSettings("Debug", os="FreeBSD", arch="x86",
                                          compiler_name="clang", libcxx="libc++", version="3.8")
        env = ConfigureEnvironment(MockConanfile(freebsd_s_clang_32))
        self.assertEquals(env.compile_flags, '-m32 -framework thing -framework thing2'
                                             ' -g -DMYDEF1 -DMYDEF2 -I"path/to/includes/lib1" '
                                             '-I"path/to/includes/lib2" -L"path/to/lib1" '
                                             '-L"path/to/lib2" -llib1 -llib2 cppflag1 '
                                             '-stdlib=libc++')

        freebsd_s_clang_64 = MockSettings("Debug", os="FreeBSD", arch="x86_64",
                                          compiler_name="clang", libcxx="libc++", version="3.8")
        env = ConfigureEnvironment(MockConanfile(freebsd_s_clang_64))
        self.assertEquals(env.compile_flags, '-m64 -framework thing -framework thing2'
                                             ' -g -DMYDEF1 -DMYDEF2 -I"path/to/includes/lib1" '
                                             '-I"path/to/includes/lib2" -L"path/to/lib1" '
                                             '-L"path/to/lib2" -llib1 -llib2 cppflag1 -stdlib=libc++')

        solaris_s_sun_cc_32 = MockSettings("Debug", os="SunOS", arch="x86",
                                           compiler_name="sun-cc", libcxx="libCstd", version="5.10")
        env = ConfigureEnvironment(MockConanfile(solaris_s_sun_cc_32))
        self.assertEquals(env.compile_flags, '-m32 -framework thing -framework thing2'
                                             ' -g -DMYDEF1 -DMYDEF2 -I"path/to/includes/lib1" '
                                             '-I"path/to/includes/lib2" -L"path/to/lib1" '
                                             '-L"path/to/lib2" -llib1 -llib2 cppflag1 -library=Cstd')

        solaris_s_sun_cc_64 = MockSettings("Debug", os="SunOS", arch="x86_64",
                                           compiler_name="sun-cc", libcxx="libCstd", version="5.10")
        env = ConfigureEnvironment(MockConanfile(solaris_s_sun_cc_64))
        self.assertEquals(env.compile_flags, '-m64 -framework thing -framework thing2'
                                             ' -g -DMYDEF1 -DMYDEF2 -I"path/to/includes/lib1" '
                                             '-I"path/to/includes/lib2" -L"path/to/lib1" '
                                             '-L"path/to/lib2" -llib1 -llib2 cppflag1 -library=Cstd')

        solaris_s_sun_cc_stlport = MockSettings("Debug", os="SunOS", arch="x86_64",
                                                compiler_name="sun-cc", libcxx="libstlport",
                                                version="5.10")
        env = ConfigureEnvironment(MockConanfile(solaris_s_sun_cc_stlport))
        self.assertEquals(env.compile_flags, '-m64 -framework thing -framework thing2'
                                             ' -g -DMYDEF1 -DMYDEF2 -I"path/to/includes/lib1" '
                                             '-I"path/to/includes/lib2" -L"path/to/lib1" '
                                             '-L"path/to/lib2" -llib1 -llib2 cppflag1 -library=stlport4')

        solaris_s_sun_cc_stdcxx = MockSettings("Debug", os="SunOS", arch="x86_64",
                                               compiler_name="sun-cc", libcxx="libstdcxx",
                                               version="5.10")
        env = ConfigureEnvironment(MockConanfile(solaris_s_sun_cc_stdcxx))
        self.assertEquals(env.compile_flags, '-m64 -framework thing -framework thing2'
                                             ' -g -DMYDEF1 -DMYDEF2 -I"path/to/includes/lib1" '
                                             '-I"path/to/includes/lib2" -L"path/to/lib1" '
                                             '-L"path/to/lib2" -llib1 -llib2 cppflag1 -library=stdcxx4')

        solaris_s_sun_cc_sparc = MockSettings("Debug", os="SunOS", arch="sparc",
                                              compiler_name="sun-cc", libcxx="libCstd", version="5.10")
        env = ConfigureEnvironment(MockConanfile(solaris_s_sun_cc_sparc))
        self.assertEquals(env.compile_flags, '-m32 -framework thing -framework thing2'
                                             ' -g -DMYDEF1 -DMYDEF2 -I"path/to/includes/lib1" '
                                             '-I"path/to/includes/lib2" -L"path/to/lib1" '
                                             '-L"path/to/lib2" -llib1 -llib2 cppflag1 -library=Cstd')

        solaris_s_sun_cc_sparcv9 = MockSettings("Debug", os="SunOS", arch="sparcv9",
                                                compiler_name="sun-cc", libcxx="libCstd", version="5.10")
        env = ConfigureEnvironment(MockConanfile(solaris_s_sun_cc_sparcv9))
        self.assertEquals(env.compile_flags, '-m64 -framework thing -framework thing2'
                                             ' -g -DMYDEF1 -DMYDEF2 -I"path/to/includes/lib1" '
                                             '-I"path/to/includes/lib2" -L"path/to/lib1" '
                                             '-L"path/to/lib2" -llib1 -llib2 cppflag1 -library=Cstd')

    def configure_environment_test(self):
        win_settings = MockSettings("Release", os="Windows", arch="x86",
                                    compiler_name="Visual Studio", libcxx=None, version="14")

        env = ConfigureEnvironment(MockConanfile(win_settings))

        if platform.system() == "Windows":
            expected = 'call ".+VC/vcvarsall.bat" x86 && call _conan_env.bat'
            self.assertRegexpMatches(env.command_line, expected)
        else:
            with self.assertRaisesRegexp(ConanException, "variable not defined"):
                env.command_line

        linux_s = MockSettings("Release", os="Linux", arch="x86",
                               compiler_name="gcc", libcxx="libstdc++", version="4.9")
        env = ConfigureEnvironment(MockConanfile(linux_s))
        self.assertEquals(env.command_line, 'env LIBS="-llib1 -llib2" LDFLAGS="-Lpath/to/lib1 '
                                            '-Lpath/to/lib2 -m32 -framework thing -framework thing2 $LDFLAGS" '
                                            'CFLAGS="$CFLAGS -m32 cflag1 -s -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'CPPFLAGS="$CPPFLAGS -m32 cppflag1 -D_GLIBCXX_USE_CXX11_ABI=0 -s -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'C_INCLUDE_PATH=$C_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2" '
                                            'CPLUS_INCLUDE_PATH=$CPLUS_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2"')

        c11settings = MockSettings("Release", os="Linux", arch="x86",
                                   compiler_name="gcc", libcxx="libstdc++11", version="6.2")
        env = ConfigureEnvironment(MockConanfile(c11settings))
        self.assertEquals(env.command_line, 'env LIBS="-llib1 -llib2" LDFLAGS="-Lpath/to/lib1 '
                                            '-Lpath/to/lib2 -m32 -framework thing -framework thing2 $LDFLAGS" '
                                            'CFLAGS="$CFLAGS -m32 cflag1 -s -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'CPPFLAGS="$CPPFLAGS -m32 cppflag1 -D_GLIBCXX_USE_CXX11_ABI=1 -s -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'C_INCLUDE_PATH=$C_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2" '
                                            'CPLUS_INCLUDE_PATH=$CPLUS_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2"')

        clang_settings_64 = MockSettings("Release", os="Macos", arch="x86_64",
                                         compiler_name="clang", libcxx="libc++", version="3.8")
        env = ConfigureEnvironment(MockConanfile(clang_settings_64))
        self.assertEquals(env.command_line, 'env LIBS="-llib1 -llib2" LDFLAGS="-Lpath/to/lib1 '
                                            '-Lpath/to/lib2 -m64 -framework thing -framework thing2 $LDFLAGS" '
                                            'CFLAGS="$CFLAGS -m64 cflag1 -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'CPPFLAGS="$CPPFLAGS -m64 cppflag1 -stdlib=libc++ -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'C_INCLUDE_PATH=$C_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2" '
                                            'CPLUS_INCLUDE_PATH=$CPLUS_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2"')

        clang_settings_std = MockSettings("Release", os="Macos", arch="x86_64",
                                          compiler_name="clang", libcxx="libstdc", version="3.8")
        env = ConfigureEnvironment(MockConanfile(clang_settings_std))
        self.assertEquals(env.command_line, 'env LIBS="-llib1 -llib2" LDFLAGS="-Lpath/to/lib1 '
                                            '-Lpath/to/lib2 -m64 -framework thing -framework thing2 $LDFLAGS" '
                                            'CFLAGS="$CFLAGS -m64 cflag1 -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'CPPFLAGS="$CPPFLAGS -m64 cppflag1 -stdlib=libstdc++ -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'C_INCLUDE_PATH=$C_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2" '
                                            'CPLUS_INCLUDE_PATH=$CPLUS_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2"')

        clang_settings_std_debug = MockSettings("Debug", os="Macos", arch="x86",
                                                compiler_name="clang", libcxx="libstdc", version="3.8")
        env = ConfigureEnvironment(MockConanfile(clang_settings_std_debug))
        self.assertEquals(env.command_line, 'env LIBS="-llib1 -llib2" LDFLAGS="-Lpath/to/lib1 '
                                            '-Lpath/to/lib2 -m32 -framework thing -framework thing2 $LDFLAGS" '
                                            'CFLAGS="$CFLAGS -m32 cflag1 -g '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'CPPFLAGS="$CPPFLAGS -m32 cppflag1 -stdlib=libstdc++ -g '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'C_INCLUDE_PATH=$C_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2" '
                                            'CPLUS_INCLUDE_PATH=$CPLUS_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2"')

        freebsd_settings = MockSettings("Release", os="FreeBSD", arch="x86",
                                        compiler_name="clang", libcxx="libc++", version="3.8")
        env = ConfigureEnvironment(MockConanfile(freebsd_settings))
        self.assertEquals(env.command_line, 'env LIBS="-llib1 -llib2" LDFLAGS="-Lpath/to/lib1 '
                                            '-Lpath/to/lib2 -m32 -framework thing -framework thing2 $LDFLAGS" '
                                            'CFLAGS="$CFLAGS -m32 cflag1 -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'CPPFLAGS="$CPPFLAGS -m32 cppflag1 -stdlib=libc++ -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'C_INCLUDE_PATH=$C_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2" '
                                            'CPLUS_INCLUDE_PATH=$CPLUS_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2"')

        solaris_settings = MockSettings("Release", os="SunOS", arch="x86_64",
                                        compiler_name="sun-cc", libcxx="libstlport", version="5.10")
        env = ConfigureEnvironment(MockConanfile(solaris_settings))
        self.assertEquals(env.command_line, 'env LIBS="-llib1 -llib2" LDFLAGS="-Lpath/to/lib1 '
                                            '-Lpath/to/lib2 -m64 -framework thing -framework thing2 $LDFLAGS" '
                                            'CFLAGS="$CFLAGS -m64 cflag1 -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'CPPFLAGS="$CPPFLAGS -m64 cppflag1 -library=stlport4 -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'C_INCLUDE_PATH=$C_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2" '
                                            'CPLUS_INCLUDE_PATH=$CPLUS_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2"')

        solaris_sparc_settings = MockSettings("Release", os="SunOS", arch="sparc",
                                              compiler_name="sun-cc", libcxx="libstlport", version="5.10")
        env = ConfigureEnvironment(MockConanfile(solaris_sparc_settings))
        self.assertEquals(env.command_line, 'env LIBS="-llib1 -llib2" LDFLAGS="-Lpath/to/lib1 '
                                            '-Lpath/to/lib2 -m32 -framework thing -framework thing2 $LDFLAGS" '
                                            'CFLAGS="$CFLAGS -m32 cflag1 -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'CPPFLAGS="$CPPFLAGS -m32 cppflag1 -library=stlport4 -DNDEBUG '
                                            '-Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2" '
                                            'C_INCLUDE_PATH=$C_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2" '
                                            'CPLUS_INCLUDE_PATH=$CPLUS_INCLUDE_PATH:"path/to/includes/lib1":'
                                            '"path/to/includes/lib2"')

        # Not supported yet
        win_gcc = MockSettings("Release", os="Windows", arch="x86",
                               compiler_name="gcc", libcxx=None, version="4.9")
        env = ConfigureEnvironment(MockConanfile(win_gcc))
        self.assertEquals(env.command_line_env, 'call _conan_env.bat')

    def gcc_test(self):
        c11settings_release = MockSettings("Release", os="Linux", arch="x86",
                                           compiler_name="gcc", libcxx="libstdc++11",
                                           version="6.2")
        gcc = GCC(c11settings_release)
        self.assertEquals(gcc.command_line, "-s -DNDEBUG -m32")

        c11settings_debug = MockSettings("Debug", os="Linux", arch="x86",
                                         compiler_name="gcc", libcxx="libstdc++",
                                         version="6.2")
        gcc = GCC(c11settings_debug)
        self.assertEquals(gcc.command_line, "-g -m32")

    def append_variables_test(self):
        output = TestBufferConanOutput()
        runner = ConanRunner()
        if platform.system() != "Windows":
            os.environ["LDFLAGS"] = "ldflag=23 otherldflag=33"
            os.environ["CPPFLAGS"] = "-cppflag -othercppflag"
            os.environ["CFLAGS"] = "-cflag"
            os.environ["C_INCLUDE_PATH"] = "/path/to/c_include_path:/anotherpath"
            os.environ["CPLUS_INCLUDE_PATH"] = "/path/to/cpp_include_path:/anotherpathpp"
            c11settings_release = MockSettings("Release", os="Linux", arch="x86",
                                               compiler_name="gcc", libcxx="libstdc++11",
                                               version="6.2")
            env = ConfigureEnvironment(MockConanfile(c11settings_release))
            runner(env.command_line, output=output)
            self.assertIn("LDFLAGS=-Lpath/to/lib1 -Lpath/to/lib2 -m32 -framework thing -framework thing2 ldflag=23 otherldflag=33\n", output)
            self.assertIn("CPPFLAGS=-cppflag -othercppflag -m32 cppflag1 -D_GLIBCXX_USE_CXX11_ABI=1 -s -DNDEBUG -Ipath/to/includes/lib1 -Ipath/to/includes/lib2 -DMYDEF1 -DMYDEF2\n", output)
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

            win_settings = MockSettings("Release", os="Windows", arch="x86",
                                        compiler_name="Visual Studio", libcxx=None,
                                        version="12")
            env = ConfigureEnvironment(MockConanfile(win_settings))
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
                             {},  # undefined scope do not apply to my packages
                             {"CXX": "/path/tomy/g++_build", "CC": "/path/tomy/gcc_build"})

        self.client.save({CONANFILE: conanfile_dep})
        self.client.run("export lasote/testing")

        self.client.save({CONANFILE: conanfile_scope_env}, clean_first=True)
        self.client.run("install --build=missing --pr scopes_env")
        self.client.run("build")
        self.assertRegexpMatches(str(self.client.user_io.out), "PATH=['\"]*/path/to/my/folder")
        self._assert_env_variable_printed("CC", "/path/tomy/gcc_build")
        self._assert_env_variable_printed("CXX", "/path/tomy/g++_build")

    def _assert_env_variable_printed(self, name, value):
        self.assertIn("%s=%s" % (name, value), self.client.user_io.out)

    def _create_profile(self, name, settings, scopes=None, env=None):
        env = env or {}
        profile = Profile()
        profile._settings = settings or {}
        if scopes:
            profile.scopes = Scopes.from_list(["%s=%s" % (key, value) for key, value in scopes.items()])
        for varname, value in env.items():
            profile.env_values.add(varname, value)
        save(os.path.join(self.client.client_cache.profiles_path, name), profile.dumps())
