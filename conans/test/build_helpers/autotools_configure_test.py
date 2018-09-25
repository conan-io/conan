import os
import platform
import unittest
from collections import namedtuple

from conans import tools
from conans.client.build.autotools_environment import AutoToolsBuildEnvironment
from conans.client.tools.oss import cpu_count
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.paths import CONANFILE
from conans.test.build_helpers.cmake_test import ConanFileMock
from conans.test.util.tools_test import RunnerMock
from conans.test.utils.conanfile import MockConanfile, MockSettings, MockOptions
from conans.test.utils.tools import TestClient


class AutoToolsConfigureTest(unittest.TestCase):

    def _set_deps_info(self, conanfile):
        conanfile.deps_cpp_info.include_paths.append("path/includes")
        conanfile.deps_cpp_info.include_paths.append("other\include\path")
        # To test some path in win, to be used with MinGW make or MSYS etc
        conanfile.deps_cpp_info.lib_paths.append("one\lib\path")
        conanfile.deps_cpp_info.libs.append("onelib")
        conanfile.deps_cpp_info.libs.append("twolib")
        conanfile.deps_cpp_info.defines.append("onedefinition")
        conanfile.deps_cpp_info.defines.append("twodefinition")
        conanfile.deps_cpp_info.cflags.append("a_c_flag")
        conanfile.deps_cpp_info.cppflags.append("a_cpp_flag")
        conanfile.deps_cpp_info.sharedlinkflags.append("shared_link_flag")
        conanfile.deps_cpp_info.exelinkflags.append("exe_link_flag")
        conanfile.deps_cpp_info.sysroot = "/path/to/folder"

    def partial_build_test(self):
        conan_file = ConanFileMock()
        deps_cpp_info = namedtuple("Deps", "libs, include_paths, lib_paths, defines, cflags, "
                                   "cppflags, sharedlinkflags, exelinkflags, sysroot")
        conan_file.deps_cpp_info = deps_cpp_info([], [], [], [], [], [], [], [], "")
        conan_file.settings = Settings()
        be = AutoToolsBuildEnvironment(conan_file)
        conan_file.should_configure = False
        conan_file.should_build = False
        conan_file.should_install = False
        be.configure()
        self.assertIsNone(conan_file.command)
        be.make()
        self.assertIsNone(conan_file.command)

    def warn_when_no_triplet_test(self):
        conan_file = ConanFileMock()
        deps_cpp_info = namedtuple("Deps", "libs, include_paths, lib_paths, defines, cflags, "
                                   "cppflags, sharedlinkflags, exelinkflags, sysroot")
        conan_file.deps_cpp_info = deps_cpp_info([], [], [], [], [], [], [], [], "")
        conan_file.settings = MockSettings({"arch": "UNKNOWN_ARCH", "os": "Linux"})
        AutoToolsBuildEnvironment(conan_file)
        self.assertIn("Unknown 'UNKNOWN_ARCH' machine, Conan doesn't know "
                      "how to translate it to the GNU triplet", conan_file.output)

    def test_cppstd(self):
        options = MockOptions({})
        # Valid one for GCC
        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86",
                                 "compiler": "gcc",
                                 "compiler.libcxx": "libstdc++11",
                                 "compiler.version": "7.1",
                                 "cppstd": "17"})
        conanfile = MockConanfile(settings, options)
        be = AutoToolsBuildEnvironment(conanfile)
        expected = be.vars["CXXFLAGS"]
        self.assertIn("-std=c++17", expected)

        # Invalid one for GCC
        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86",
                                 "compiler": "gcc",
                                 "compiler.libcxx": "libstdc++11",
                                 "compiler.version": "4.9",
                                 "cppstd": "17"})
        conanfile = MockConanfile(settings, options)
        be = AutoToolsBuildEnvironment(conanfile)
        expected = be.vars["CXXFLAGS"]
        self.assertNotIn("-std", expected)

        # Valid one for Clang
        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86",
                                 "compiler": "clang",
                                 "compiler.libcxx": "libstdc++11",
                                 "compiler.version": "4.0",
                                 "cppstd": "17"})
        conanfile = MockConanfile(settings, options)
        be = AutoToolsBuildEnvironment(conanfile)
        expected = be.vars["CXXFLAGS"]
        self.assertIn("-std=c++1z", expected)

        # Invalid one for Clang
        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86",
                                 "compiler": "clang",
                                 "compiler.libcxx": "libstdc++11",
                                 "compiler.version": "3.3",
                                 "cppstd": "17"})
        conanfile = MockConanfile(settings, options)
        be = AutoToolsBuildEnvironment(conanfile)
        expected = be.vars["CXXFLAGS"]
        self.assertNotIn("-std=", expected)

        # Visual Activate 11 is useless
        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "15",
                                 "cppstd": "11"})
        conanfile = MockConanfile(settings, options)
        be = AutoToolsBuildEnvironment(conanfile)
        expected = be.vars["CXXFLAGS"]
        self.assertNotIn("-std=c++", expected)

        # Visual Activate 17 in VS 2017
        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "15",
                                 "cppstd": "17"})
        conanfile = MockConanfile(settings, options)
        be = AutoToolsBuildEnvironment(conanfile)
        expected = be.vars["CXXFLAGS"]
        self.assertIn("/std:c++17", expected)

        # Visual Activate 17 in VS 2015
        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "14",
                                 "cppstd": "17"})
        conanfile = MockConanfile(settings, options)
        be = AutoToolsBuildEnvironment(conanfile)
        expected = be.vars["CXXFLAGS"]
        self.assertIn("/std:c++latest", expected)

    def test_mocked_methods(self):

        runner = RunnerMock()
        conanfile = MockConanfile(MockSettings({}), None, runner)
        ab = AutoToolsBuildEnvironment(conanfile)
        ab.make(make_program="othermake")
        self.assertEquals(runner.command_called, "othermake -j%s" % cpu_count())

        with tools.environment_append({"CONAN_MAKE_PROGRAM": "mymake"}):
            ab.make(make_program="othermake")
            self.assertEquals(runner.command_called, "mymake -j%s" % cpu_count())

        ab.make(args=["things"])
        things = "'things'" if platform.system() != "Windows" else "things"
        self.assertEquals(runner.command_called, "make %s -j%s" % (things, cpu_count()))

    def test_variables(self):
        # Visual Studio
        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "14",
                                 "compiler.runtime": "MD"})
        conanfile = MockConanfile(settings)
        self._set_deps_info(conanfile)

        be = AutoToolsBuildEnvironment(conanfile)
        expected = {'CFLAGS': 'a_c_flag -O2 -Ob2',
                    'CPPFLAGS': '-Ipath\\includes -Iother\\include\\path -Donedefinition -Dtwodefinition -DNDEBUG',
                    'CXXFLAGS': 'a_c_flag -O2 -Ob2 a_cpp_flag',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -LIBPATH:one\\lib\\path',
                    'LIBS': 'onelib.lib twolib.lib'}

        self.assertEquals(be.vars, expected)
        # GCC 32
        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86",
                                 "compiler": "gcc",
                                 "compiler.libcxx": "libstdc++"})
        conanfile = MockConanfile(settings)
        self._set_deps_info(conanfile)

        be = AutoToolsBuildEnvironment(conanfile)
        expected = {'CFLAGS': 'a_c_flag -m32 -O3 -s --sysroot=/path/to/folder',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition -DNDEBUG '
                                '-D_GLIBCXX_USE_CXX11_ABI=0',
                    'CXXFLAGS': 'a_c_flag -m32 -O3 -s --sysroot=/path/to/folder a_cpp_flag',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m32 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib'}

        self.assertEquals(be.vars, expected)

        # GCC 64
        settings = MockSettings({"build_type": "Debug",
                                 "arch": "x86_64",
                                 "compiler": "gcc",
                                 "compiler.libcxx": "libstdc++"})
        conanfile = MockConanfile(settings)
        conanfile.settings = settings
        self._set_deps_info(conanfile)
        expected = {'CFLAGS': 'a_c_flag -m64 -g --sysroot=/path/to/folder',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition'
                                ' -D_GLIBCXX_USE_CXX11_ABI=0',
                    'CXXFLAGS': 'a_c_flag -m64 -g --sysroot=/path/to/folder a_cpp_flag',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEquals(be.vars, expected)

        # With clang, we define _GLIBCXX_USE_CXX11_ABI
        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86_64",
                                 "compiler": "clang",
                                 "compiler.libcxx": "libstdc++"})
        conanfile = MockConanfile(settings)
        conanfile.settings = settings
        self._set_deps_info(conanfile)
        expected = {'CFLAGS': 'a_c_flag -m64 -O3 --sysroot=/path/to/folder',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition'
                                ' -DNDEBUG -D_GLIBCXX_USE_CXX11_ABI=0',
                    'CXXFLAGS': 'a_c_flag -m64 -O3 --sysroot=/path/to/folder a_cpp_flag -stdlib=libstdc++',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEquals(be.vars, expected)

        # Change libcxx
        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86_64",
                                 "compiler": "clang",
                                 "compiler.libcxx": "libc++"})
        conanfile = MockConanfile(settings)
        conanfile.settings = settings
        self._set_deps_info(conanfile)
        expected = {'CFLAGS': 'a_c_flag -m64 -O3 --sysroot=/path/to/folder',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition -DNDEBUG',
                    'CXXFLAGS': 'a_c_flag -m64 -O3 --sysroot=/path/to/folder a_cpp_flag -stdlib=libc++',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEquals(be.vars, expected)

        # gcc libcxx
        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86_64",
                                 "compiler": "gcc",
                                 "compiler.libcxx": "libstdc++11"})
        conanfile = MockConanfile(settings)
        conanfile.settings = settings
        self._set_deps_info(conanfile)
        expected = {'CFLAGS': 'a_c_flag -m64 -O3 -s --sysroot=/path/to/folder',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition -DNDEBUG '
                                '-D_GLIBCXX_USE_CXX11_ABI=1',
                    'CXXFLAGS': 'a_c_flag -m64 -O3 -s --sysroot=/path/to/folder a_cpp_flag',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEquals(be.vars, expected)

        # Sun CC libCstd
        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86_64",
                                 "compiler": "sun-cc",
                                 "compiler.libcxx": "libCstd"})
        conanfile = MockConanfile(settings)
        conanfile.settings = settings
        self._set_deps_info(conanfile)
        expected = {'CFLAGS': 'a_c_flag -m64 -xO3 --sysroot=/path/to/folder',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition -DNDEBUG',
                    'CXXFLAGS': 'a_c_flag -m64 -xO3 --sysroot=/path/to/folder a_cpp_flag -library=Cstd',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEquals(be.vars, expected)

        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86_64",
                                 "compiler": "sun-cc",
                                 "compiler.libcxx": "libstdcxx"})
        conanfile = MockConanfile(settings)
        conanfile.settings = settings
        self._set_deps_info(conanfile)
        expected = {'CFLAGS': 'a_c_flag -m64 -xO3 --sysroot=/path/to/folder',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition -DNDEBUG',
                    'CXXFLAGS': 'a_c_flag -m64 -xO3 --sysroot=/path/to/folder a_cpp_flag -library=stdcxx4',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEquals(be.vars, expected)

        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86_64",
                                 "compiler": "sun-cc",
                                 "compiler.libcxx": "libstlport"})
        conanfile = MockConanfile(settings)
        conanfile.settings = settings
        self._set_deps_info(conanfile)
        expected = {'CFLAGS': 'a_c_flag -m64 -xO3 --sysroot=/path/to/folder',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition -DNDEBUG',
                    'CXXFLAGS': 'a_c_flag -m64 -xO3 --sysroot=/path/to/folder a_cpp_flag -library=stlport4',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEquals(be.vars, expected)

        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86_64",
                                 "compiler": "sun-cc",
                                 "compiler.libcxx": "libstdc++"})
        conanfile = MockConanfile(settings)
        conanfile.settings = settings
        self._set_deps_info(conanfile)
        expected = {'CFLAGS': 'a_c_flag -m64 -xO3 --sysroot=/path/to/folder',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition -DNDEBUG',
                    'CXXFLAGS': 'a_c_flag -m64 -xO3 --sysroot=/path/to/folder a_cpp_flag -library=stdcpp',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEquals(be.vars, expected)

    def rpath_optin_test(self):
        settings = MockSettings({"os_build": "Linux",
                                 "build_type": "Release",
                                 "arch": "x86_64",
                                 "compiler": "gcc",
                                 "compiler.libcxx": "libstdc++11"})
        conanfile = MockConanfile(settings)
        conanfile.settings = settings
        self._set_deps_info(conanfile)
        expected = {'CFLAGS': 'a_c_flag -m64 -O3 -s --sysroot=/path/to/folder',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition -DNDEBUG '
                                '-D_GLIBCXX_USE_CXX11_ABI=1',
                    'CXXFLAGS': 'a_c_flag -m64 -O3 -s --sysroot=/path/to/folder a_cpp_flag',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 --sysroot=/path/to/folder '
                               '-Wl,-rpath="one/lib/path" -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib'}
        be = AutoToolsBuildEnvironment(conanfile, include_rpath_flags=True)
        self.assertEquals(be.vars, expected)

    def environment_append_test(self):
        settings = MockSettings({"build_type": "Debug",
                                 "arch": "x86_64",
                                 "compiler": "gcc",
                                 "compiler.libcxx": "libstdc++"})
        conanfile = MockConanfile(settings)
        conanfile.settings = settings
        self._set_deps_info(conanfile)
        env_vars = {"CFLAGS": "-additionalcflag",
                    "CXXFLAGS": "-additionalcxxflag",
                    "LDFLAGS": "-additionalldflag",
                    "LIBS": "-additionallibs",
                    "CPPFLAGS": "-additionalcppflag"}

        with(tools.environment_append(env_vars)):
            be = AutoToolsBuildEnvironment(conanfile)
            expected = {'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -'
                                    'Dtwodefinition -D_GLIBCXX_USE_CXX11_ABI=0 -additionalcppflag',
                        'CXXFLAGS': 'a_c_flag -m64 -g --sysroot=/path/to/folder a_cpp_flag -additionalcxxflag',
                        'LIBS': '-lonelib -ltwolib -additionallibs',
                        'LDFLAGS': 'shared_link_flag exe_link_flag -m64 '
                                   '--sysroot=/path/to/folder -Lone/lib/path -additionalldflag',
                        'CFLAGS': 'a_c_flag -m64 -g --sysroot=/path/to/folder -additionalcflag'}
            self.assertEquals(be.vars, expected)

    def modify_values_test(self):
        settings = MockSettings({"build_type": "Debug",
                                 "arch": "x86_64",
                                 "compiler": "gcc",
                                 "compiler.libcxx": "libstdc++"})
        conanfile = MockConanfile(settings)
        conanfile.settings = settings
        self._set_deps_info(conanfile)
        be = AutoToolsBuildEnvironment(conanfile)

        # Alter some things
        be.defines.append("OtherDefinition=23")
        be.link_flags = ["-inventedflag"]
        be.cxx_flags.append("-onlycxx")
        be.fpic = True
        be.flags.append("cucucu")

        expected = {'CFLAGS': 'a_c_flag -m64 -g --sysroot=/path/to/folder cucucu -fPIC',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition'
                                ' -D_GLIBCXX_USE_CXX11_ABI=0 -DOtherDefinition=23',
                    'CXXFLAGS': 'a_c_flag -m64 -g --sysroot=/path/to/folder cucucu -fPIC a_cpp_flag -onlycxx',
                    'LDFLAGS': '-inventedflag -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib'}
        self.assertEquals(be.vars, expected)

    def test_previous_env(self):
        settings = MockSettings({"arch": "x86",
                                 "os": "Linux",
                                 "compiler": "gcc"})
        conanfile = MockConanfile(settings)

        with tools.environment_append({"CPPFLAGS": "MyCppFlag"}):
            be = AutoToolsBuildEnvironment(conanfile)
            self.assertEquals(be.vars["CPPFLAGS"], "MyCppFlag")

    def test_pkg_config_paths(self):
        if platform.system() == "Windows":
            return
        client = TestClient()
        conanfile = """
from conans import ConanFile, tools, AutoToolsBuildEnvironment

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2.1"
    generators = %s

    def build(self):
        tools.save("configure", "printenv")
        self.run("chmod +x configure")
        autot = AutoToolsBuildEnvironment(self)
        autot.configure(%s)

"""

        client.save({CONANFILE: conanfile % ("'txt'", "")})
        client.run("create . conan/testing")
        self.assertNotIn("PKG_CONFIG_PATH=", client.out)

        ref = ConanFileReference.loads("Hello/1.2.1@conan/testing")
        builds_folder = client.client_cache.builds(ref)
        bf = os.path.join(builds_folder, os.listdir(builds_folder)[0])

        client.save({CONANFILE: conanfile % ("'pkg_config'", "")})
        client.run("create . conan/testing")
        self.assertIn("PKG_CONFIG_PATH=%s" % bf, client.out)

        # The previous values in the environment should be kept too
        with tools.environment_append({"PKG_CONFIG_PATH": "Some/value"}):
            client.run("create . conan/testing")
            self.assertIn("PKG_CONFIG_PATH=%s:Some/value" % bf, client.out)

        client.save({CONANFILE: conanfile % ("'pkg_config'",
                                             "pkg_config_paths=['/tmp/hello', 'foo']")})
        client.run("create . conan/testing")
        self.assertIn("PKG_CONFIG_PATH=/tmp/hello:%s/foo" % bf, client.out)

        # The previous values in the environment should be kept too
        with tools.environment_append({"PKG_CONFIG_PATH": "Some/value"}):
            client.run("create . conan/testing")
            self.assertIn("PKG_CONFIG_PATH=/tmp/hello:%s/foo:Some/value" % bf, client.out)

    def cross_build_command_test(self):
        runner = RunnerMock()
        conanfile = MockConanfile(MockSettings({}), None, runner)
        ab = AutoToolsBuildEnvironment(conanfile)
        self.assertFalse(ab.build)
        self.assertFalse(ab.host)
        self.assertFalse(ab.target)

        ab.configure()
        self.assertEquals(runner.command_called, "./configure  ")

        ab.configure(host="x86_64-apple-darwin")
        self.assertEquals(runner.command_called, "./configure  --host=x86_64-apple-darwin")

        ab.configure(build="arm-apple-darwin")
        self.assertEquals(runner.command_called, "./configure  --build=arm-apple-darwin")

        ab.configure(target="i686-apple-darwin")
        self.assertEquals(runner.command_called, "./configure  --target=i686-apple-darwin")

        conanfile = MockConanfile(MockSettings({"build_type": "Debug",
                                                "arch": "x86_64",
                                                "os": "Windows",
                                                "compiler": "gcc",
                                                "compiler.libcxx": "libstdc++"}),
                                  None, runner)
        ab = AutoToolsBuildEnvironment(conanfile)
        ab.configure()
        if platform.system() == "Windows":
            # Not crossbuilding
            self.assertFalse(ab.host)
            self.assertFalse(ab.build)
            self.assertIn("./configure", runner.command_called)
            self.assertNotIn("--build=x86_64-w64-mingw32 --host=x86_64-w64-mingw32",
                             runner.command_called)
        elif platform.system() == "Linux":
            self.assertIn("x86_64-w64-mingw32", ab.host)
            self.assertIn("x86_64-linux-gnu", ab.build)
            self.assertIn("./configure  --build=x86_64-linux-gnu --host=x86_64-w64-mingw32",
                          runner.command_called)
        else:
            self.assertIn("x86_64-w64-mingw32", ab.host)
            self.assertIn("x86_64-apple-darwin", ab.build)
            self.assertIn("./configure  --build=x86_64-apple-darwin --host=x86_64-w64-mingw32",
                          runner.command_called)

        ab.configure(build="fake_build_triplet", host="fake_host_triplet")
        self.assertIn("./configure  --build=fake_build_triplet --host=fake_host_triplet",
                      runner.command_called)

        ab.build = "superfake_build_triplet"
        ab.host = "superfake_host_triplet"
        ab.configure()
        self.assertIn("./configure  --build=superfake_build_triplet --host=superfake_host_triplet",
                      runner.command_called)

    def test_make_targets_install(self):
        runner = RunnerMock()
        conanfile = MockConanfile(MockSettings({}), None, runner)

        ab = AutoToolsBuildEnvironment(conanfile)
        ab.configure()

        ab.make(target="install")
        self.assertEquals(runner.command_called, "make install -j%s" % cpu_count())
        ab.install()
        self.assertEquals(runner.command_called, "make install -j%s" % cpu_count())

    def autotools_prefix_libdir_test(self):
        runner = RunnerMock()
        conanfile = MockConanfile(MockSettings({}), None, runner)
        # Package folder is not defined
        ab = AutoToolsBuildEnvironment(conanfile)
        ab.configure()
        self.assertNotIn("--prefix", runner.command_called)
        self.assertNotIn("--libdir", runner.command_called)
        # package folder defined
        conanfile.package_folder = "/package_folder"
        ab.configure()
        if platform.system() == "Windows":
            self.assertIn("./configure --prefix=/package_folder --libdir=${prefix}/lib",
                          runner.command_called)
        else:
            self.assertIn("./configure '--prefix=/package_folder' '--libdir=${prefix}/lib'",
                          runner.command_called)
        # --prefix already used in args
        ab.configure(args=["--prefix=/my_package_folder"])
        if platform.system() == "Windows":
            self.assertIn("./configure --prefix=/my_package_folder --libdir=${prefix}/lib",
                          runner.command_called)
            self.assertNotIn("--prefix=/package_folder", runner.command_called)
        else:
            self.assertIn("./configure '--prefix=/my_package_folder' '--libdir=${prefix}/lib'",
                          runner.command_called)
            self.assertNotIn("'--prefix=/package_folder'", runner.command_called)
        # --libdir already used in args
        ab.configure(args=["--libdir=/my_package_folder/superlibdir"])
        if platform.system() == "Windows":
            self.assertIn("./configure --libdir=/my_package_folder/superlibdir "
                          "--prefix=/package_folder", runner.command_called)
            self.assertNotIn("--libdir=${prefix}/lib", runner.command_called)
        else:
            self.assertIn("./configure '--libdir=/my_package_folder/superlibdir' "
                          "'--prefix=/package_folder'", runner.command_called)
            self.assertNotIn("'--libdir=${prefix}/lib'", runner.command_called)

    def autotools_configure_vars_test(self):
        from mock import patch

        runner = RunnerMock()
        settings = MockSettings({"build_type": "Debug",
                                 "arch": "x86_64",
                                 "compiler": "gcc",
                                 "compiler.libcxx": "libstdc++"})
        conanfile = MockConanfile(settings, None, runner)
        conanfile.settings = settings
        self._set_deps_info(conanfile)

        def custom_configure(obj, configure_dir=None, args=None, build=None, host=None, target=None,
                             pkg_config_paths=None, vars=None):  # @UnusedVariable
            self.assertNotEqual(obj.vars, vars)
            return vars or obj.vars

        with patch.object(AutoToolsBuildEnvironment, 'configure', new=custom_configure):
            be = AutoToolsBuildEnvironment(conanfile)

            # Get vars and modify them
            my_vars = be.vars
            my_vars["fake_var"] = "fake"
            my_vars["super_fake_var"] = "fakefake"

            # TEST with default vars
            mocked_result = be.configure()
            self.assertEqual(mocked_result, be.vars)

            # TEST with custom vars
            mocked_result = be.configure(vars=my_vars)
            self.assertEqual(mocked_result, my_vars)

    def autotools_fpic_test(self):
        runner = None
        settings = MockSettings({"os": "Linux"})
        options = MockOptions({"fPIC": True, "shared": False})
        conanfile = MockConanfile(settings, options, runner)
        ab = AutoToolsBuildEnvironment(conanfile)
        self.assertTrue(ab.fpic)

        options = MockOptions({"fPIC": True, "shared": True})
        conanfile = MockConanfile(settings, options, runner)
        ab = AutoToolsBuildEnvironment(conanfile)
        self.assertTrue(ab.fpic)

        options = MockOptions({"fPIC": False, "shared": True})
        conanfile = MockConanfile(settings, options, runner)
        ab = AutoToolsBuildEnvironment(conanfile)
        self.assertTrue(ab.fpic)

        options = MockOptions({"fPIC": False, "shared": False})
        conanfile = MockConanfile(settings, options, runner)
        ab = AutoToolsBuildEnvironment(conanfile)
        self.assertFalse(ab.fpic)

        settings = MockSettings({"os": "Windows"})
        options = MockOptions({"fPIC": True, "shared": True})
        conanfile = MockConanfile(settings, options, runner)
        ab = AutoToolsBuildEnvironment(conanfile)
        self.assertFalse(ab.fpic)

        settings = MockSettings({"os": "Macos", "compiler": "clang"})
        options = MockOptions({"fPIC": False, "shared": False})
        conanfile = MockConanfile(settings, options, runner)
        ab = AutoToolsBuildEnvironment(conanfile)
        self.assertFalse(ab.fpic)
        ab.fpic = True
        self.assertIn("-fPIC", ab.vars["CXXFLAGS"])
