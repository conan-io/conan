import platform
import unittest
from collections import namedtuple

from conans.client import tools
from conans.client.build.autotools_environment import AutoToolsBuildEnvironment
from conans.client.tools.oss import cpu_count
from conans.errors import ConanException
from conans.model.settings import Settings
from conans.test.unittests.util.tools_test import RunnerMock
from conans.test.utils.mocks import MockSettings, MockConanfile, ConanFileMock, MockOptions

default_dirs_flags = ["--bindir", "--libdir", "--includedir", "--datarootdir", "--libdir",
                      "--sbindir", "--oldincludedir", "--libexecdir"]


class MockConanfileWithOutput(MockConanfile):
    def run(self, *args, **kwargs):
        if self.runner:
            self.runner(*args, **kwargs)


class RunnerMockWithHelp(RunnerMock):

    def __init__(self, return_ok=True, available_args=None):
        self.output = None
        self.command_called = None
        self.return_ok = return_ok
        self.available_args = available_args or []

    def __call__(self, command, output=None, win_bash=False, subsystem=None):  # @UnusedVariable
        if "configure --help" in command:
            output.write(" ".join(self.available_args))
        else:
            return super(RunnerMockWithHelp, self).__call__(command, output, win_bash, subsystem)


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
        conanfile.deps_cpp_info.cxxflags.append("a_cxx_flag")
        conanfile.deps_cpp_info.sharedlinkflags.append("shared_link_flag")
        conanfile.deps_cpp_info.exelinkflags.append("exe_link_flag")
        conanfile.deps_cpp_info.sysroot = "/path/to/folder"
        conanfile.deps_cpp_info.frameworks.append("oneframework")
        conanfile.deps_cpp_info.frameworks.append("twoframework")
        conanfile.deps_cpp_info.system_libs.append("onesystemlib")
        conanfile.deps_cpp_info.system_libs.append("twosystemlib")
        conanfile.deps_cpp_info.framework_paths.append("one/framework/path")

    def _creat_deps_cpp_info(self):
        deps_cpp_info = namedtuple("Deps", "libs, include_paths, lib_paths, defines, cflags, "
                                           "cxxflags, sharedlinkflags, exelinkflags, sysroot, "
                                           "frameworks, framework_paths, system_libs")
        return deps_cpp_info([], [], [], [], [], [], [], [], "", [], [], [])

    def test_target_triple(self):
        conan_file = ConanFileMock()
        conan_file.deps_cpp_info = self._creat_deps_cpp_info()
        conan_file.settings = MockSettings({"os_target":"Linux", "arch_target":"x86_64"})
        be = AutoToolsBuildEnvironment(conan_file)
        expected = "x86_64-linux-gnu"
        self.assertEqual(be.target, expected)

    def test_partial_build(self):
        conan_file = ConanFileMock()
        conan_file.deps_cpp_info = self._creat_deps_cpp_info()
        conan_file.settings = Settings()
        be = AutoToolsBuildEnvironment(conan_file)
        conan_file.should_configure = False
        conan_file.should_build = False
        conan_file.should_install = False
        be.configure()
        self.assertIsNone(conan_file.command)
        be.make()
        self.assertIsNone(conan_file.command)

    def test_nmake_no_parallel(self):
        conan_file = ConanFileMock()
        conan_file.deps_cpp_info = self._creat_deps_cpp_info()
        conan_file.settings = Settings()
        be = AutoToolsBuildEnvironment(conan_file)
        be.make(make_program="nmake")
        assert "-j" not in conan_file.command
        be.make(make_program="make")
        assert "-j" in conan_file.command

    def test_warn_when_no_triplet(self):
        conan_file = ConanFileMock()
        conan_file.deps_cpp_info = self._creat_deps_cpp_info()
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
        self.assertEqual(runner.command_called, "othermake -j%s" %
                          cpu_count(output=conanfile.output))

        with tools.environment_append({"CONAN_MAKE_PROGRAM": "mymake"}):
            ab.make(make_program="othermake")
            self.assertEqual(runner.command_called, "mymake -j%s" %
                              cpu_count(output=conanfile.output))

        ab.make(args=["things"])
        things = "'things'" if platform.system() != "Windows" else "things"
        self.assertEqual(runner.command_called, "make %s -j%s" %
                          (things, cpu_count(output=conanfile.output)))

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
        expected = {'CFLAGS': 'a_c_flag -O2 -Ob2 -MD',
                    'CPPFLAGS': '-Ipath\\includes -Iother\\include\\path -Donedefinition -Dtwodefinition -DNDEBUG',
                    'CXXFLAGS': 'a_c_flag -O2 -Ob2 -MD a_cxx_flag',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -LIBPATH:one\\lib\\path',
                    'LIBS': 'onelib.lib twolib.lib onesystemlib.lib twosystemlib.lib'}

        self.assertEqual(be.vars, expected)
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
                    'CXXFLAGS': 'a_c_flag -m32 -O3 -s --sysroot=/path/to/folder a_cxx_flag',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -framework oneframework -framework twoframework '
                               '-F one/framework/path -m32 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib -lonesystemlib -ltwosystemlib'}

        self.assertEqual(be.vars, expected)

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
                    'CXXFLAGS': 'a_c_flag -m64 -g --sysroot=/path/to/folder a_cxx_flag',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -framework oneframework -framework twoframework '
                               '-F one/framework/path -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib -lonesystemlib -ltwosystemlib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEqual(be.vars, expected)

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
                    'CXXFLAGS': 'a_c_flag -m64 -O3 --sysroot=/path/to/folder a_cxx_flag -stdlib=libstdc++',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -framework oneframework -framework twoframework '
                               '-F one/framework/path -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib -lonesystemlib -ltwosystemlib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEqual(be.vars, expected)

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
                    'CXXFLAGS': 'a_c_flag -m64 -O3 --sysroot=/path/to/folder a_cxx_flag -stdlib=libc++',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -framework oneframework -framework twoframework '
                               '-F one/framework/path -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib -lonesystemlib -ltwosystemlib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEqual(be.vars, expected)

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
                    'CXXFLAGS': 'a_c_flag -m64 -O3 -s --sysroot=/path/to/folder a_cxx_flag',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -framework oneframework -framework twoframework '
                               '-F one/framework/path -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib -lonesystemlib -ltwosystemlib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEqual(be.vars, expected)

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
                    'CXXFLAGS': 'a_c_flag -m64 -xO3 --sysroot=/path/to/folder a_cxx_flag -library=Cstd',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib -lonesystemlib -ltwosystemlib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEqual(be.vars, expected)

        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86_64",
                                 "compiler": "sun-cc",
                                 "compiler.libcxx": "libstdcxx"})
        conanfile = MockConanfile(settings)
        conanfile.settings = settings
        self._set_deps_info(conanfile)
        expected = {'CFLAGS': 'a_c_flag -m64 -xO3 --sysroot=/path/to/folder',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition -DNDEBUG',
                    'CXXFLAGS': 'a_c_flag -m64 -xO3 --sysroot=/path/to/folder a_cxx_flag -library=stdcxx4',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib -lonesystemlib -ltwosystemlib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEqual(be.vars, expected)

        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86_64",
                                 "compiler": "sun-cc",
                                 "compiler.libcxx": "libstlport"})
        conanfile = MockConanfile(settings)
        conanfile.settings = settings
        self._set_deps_info(conanfile)
        expected = {'CFLAGS': 'a_c_flag -m64 -xO3 --sysroot=/path/to/folder',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition -DNDEBUG',
                    'CXXFLAGS': 'a_c_flag -m64 -xO3 --sysroot=/path/to/folder a_cxx_flag -library=stlport4',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib -lonesystemlib -ltwosystemlib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEqual(be.vars, expected)

        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86_64",
                                 "compiler": "sun-cc",
                                 "compiler.libcxx": "libstdc++"})
        conanfile = MockConanfile(settings)
        conanfile.settings = settings
        self._set_deps_info(conanfile)
        expected = {'CFLAGS': 'a_c_flag -m64 -xO3 --sysroot=/path/to/folder',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition -DNDEBUG',
                    'CXXFLAGS': 'a_c_flag -m64 -xO3 --sysroot=/path/to/folder a_cxx_flag -library=stdcpp',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 --sysroot=/path/to/folder -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib -lonesystemlib -ltwosystemlib'}
        be = AutoToolsBuildEnvironment(conanfile)
        self.assertEqual(be.vars, expected)

    def test_rpath_optin(self):
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
                    'CXXFLAGS': 'a_c_flag -m64 -O3 -s --sysroot=/path/to/folder a_cxx_flag',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -framework oneframework -framework twoframework '
                               '-F one/framework/path -m64 --sysroot=/path/to/folder '
                               '-Wl,-rpath,"one/lib/path" -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib -lonesystemlib -ltwosystemlib'}
        be = AutoToolsBuildEnvironment(conanfile, include_rpath_flags=True)
        self.assertEqual(be.vars, expected)

    def test_environment_append(self):
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
                        'CXXFLAGS': 'a_c_flag -m64 -g --sysroot=/path/to/folder a_cxx_flag -additionalcxxflag',
                        'LIBS': '-lonelib -ltwolib -lonesystemlib -ltwosystemlib -additionallibs',
                        'LDFLAGS': 'shared_link_flag exe_link_flag -framework oneframework '
                                   '-framework twoframework -F one/framework/path -m64 '
                                   '--sysroot=/path/to/folder -Lone/lib/path -additionalldflag',
                        'CFLAGS': 'a_c_flag -m64 -g --sysroot=/path/to/folder -additionalcflag'}
            self.assertEqual(be.vars, expected)

    def test_modify_values(self):
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
                    'CXXFLAGS': 'a_c_flag -m64 -g --sysroot=/path/to/folder cucucu -fPIC a_cxx_flag -onlycxx',
                    'LDFLAGS': '-inventedflag -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib -lonesystemlib -ltwosystemlib'}
        self.assertEqual(be.vars, expected)

    def test_previous_env(self):
        settings = MockSettings({"arch": "x86",
                                 "os": "Linux",
                                 "compiler": "gcc"})
        conanfile = MockConanfile(settings)

        with tools.environment_append({"CPPFLAGS": "MyCppFlag"}):
            be = AutoToolsBuildEnvironment(conanfile)
            self.assertEqual(be.vars["CPPFLAGS"], "MyCppFlag")

    def test_cross_build_command(self):
        runner = RunnerMock()
        conanfile = MockConanfile(MockSettings({}), None, runner)
        ab = AutoToolsBuildEnvironment(conanfile)
        self.assertFalse(ab.build)
        self.assertFalse(ab.host)
        self.assertFalse(ab.target)

        ab.configure()
        self.assertEqual(runner.command_called, "./configure  ")

        ab.configure(host="x86_64-apple-darwin")
        self.assertEqual(runner.command_called, "./configure  --host=x86_64-apple-darwin")

        ab.configure(build="arm-apple-darwin")
        self.assertEqual(runner.command_called, "./configure  --build=arm-apple-darwin")

        ab.configure(target="i686-apple-darwin")
        self.assertEqual(runner.command_called, "./configure  --target=i686-apple-darwin")

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
            build_arch = "aarch64" if platform.machine() == "arm64" else platform.machine()
            self.assertIn("x86_64-w64-mingw32", ab.host)
            self.assertIn(f"{build_arch}-apple-darwin", ab.build)
            self.assertIn(f"./configure  --build={build_arch}-apple-darwin --host=x86_64-w64-mingw32",
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
        self.assertEqual(runner.command_called, "make install -j%s" %
                          cpu_count(output=conanfile.output))
        ab.install()
        self.assertEqual(runner.command_called, "make install -j%s" %
                          cpu_count(output=conanfile.output))

    def test_autotools_install_dir_custom_configure(self):
        for flag_to_remove in default_dirs_flags:
            flags_available = set(default_dirs_flags) - set([flag_to_remove])
            runner = RunnerMockWithHelp(available_args=flags_available)
            conanfile = MockConanfileWithOutput(MockSettings({}), None, runner)
            conanfile.folders.set_base_package("/package_folder")
            ab = AutoToolsBuildEnvironment(conanfile)
            ab.configure()
            self.assertNotIn(flag_to_remove, runner.command_called)
            for flag_applied in flags_available:
                self.assertIn(flag_applied, runner.command_called)

    def test_failing_configure_help(self):

        class RunnerMockWithHelpFailing(RunnerMockWithHelp):
            def __call__(self, command, output=None, win_bash=False,
                         subsystem=None):  # @UnusedVariable
                if "configure --help" in command:
                    raise ConanException("Help not available")
                else:
                    return super(RunnerMockWithHelp, self).__call__(command, output, win_bash,
                                                                    subsystem)

        runner = RunnerMockWithHelpFailing(available_args=default_dirs_flags)
        conanfile = MockConanfileWithOutput(MockSettings({}), None, runner)
        conanfile.folders.set_base_package("/package_folder")
        ab = AutoToolsBuildEnvironment(conanfile)
        ab.configure()
        for flag_applied in default_dirs_flags:
            self.assertNotIn(flag_applied, runner.command_called)
        self.assertIn("Error running `configure --help`: Help not available", conanfile.output)

    def test_autotools_install_dirs(self):

        runner = RunnerMockWithHelp(available_args=default_dirs_flags)
        conanfile = MockConanfileWithOutput(MockSettings({}), None, runner)
        # Package folder is not defined
        ab = AutoToolsBuildEnvironment(conanfile)
        ab.configure()
        self.assertNotIn("--prefix", runner.command_called)
        self.assertNotIn("--bindir", runner.command_called)
        self.assertNotIn("--libdir", runner.command_called)
        self.assertNotIn("--includedir", runner.command_called)
        self.assertNotIn("--datarootdir", runner.command_called)
        # package folder defined
        conanfile.folders.set_base_package("/package_folder")
        ab.configure()
        if platform.system() == "Windows":
            self.assertIn("./configure --prefix=/package_folder --bindir=${prefix}/bin "
                          "--sbindir=${prefix}/bin --libexecdir=${prefix}/bin "
                          "--libdir=${prefix}/lib --includedir=${prefix}/include "
                          "--oldincludedir=${prefix}/include --datarootdir=${prefix}/share",
                          runner.command_called)
        else:
            self.assertIn("./configure '--prefix=/package_folder' '--bindir=${prefix}/bin' "
                          "'--sbindir=${prefix}/bin' '--libexecdir=${prefix}/bin' "
                          "'--libdir=${prefix}/lib' '--includedir=${prefix}/include' "
                          "'--oldincludedir=${prefix}/include' '--datarootdir=${prefix}/share'",
                          runner.command_called)
        # --prefix already used in args
        ab.configure(args=["--prefix=/my_package_folder"])
        self.assertIn("--prefix=/my_package_folder", runner.command_called)
        self.assertNotIn("--prefix=/package_folder", runner.command_called)
        # --bindir, --libdir, --includedir already used in args
        ab.configure(args=["--bindir=/pf/superbindir", "--libdir=/pf/superlibdir",
                           "--includedir=/pf/superincludedir"])
        self.assertNotIn("--bindir=${prefix}/bin", runner.command_called)
        self.assertNotIn("--libdir=${prefix}/lib", runner.command_called)
        self.assertNotIn("--includedir=${prefix}/lib", runner.command_called)
        if platform.system() == "Windows":
            self.assertIn("./configure --bindir=/pf/superbindir --libdir=/pf/superlibdir "
                          "--includedir=/pf/superincludedir --prefix=/package_folder "
                          "--sbindir=${prefix}/bin --libexecdir=${prefix}/bin "
                          "--oldincludedir=${prefix}/include --datarootdir=${prefix}/share",
                          runner.command_called)
        else:
            self.assertIn("./configure '--bindir=/pf/superbindir' '--libdir=/pf/superlibdir' "
                          "'--includedir=/pf/superincludedir' '--prefix=/package_folder' "
                          "'--sbindir=${prefix}/bin' '--libexecdir=${prefix}/bin' "
                          "'--oldincludedir=${prefix}/include' '--datarootdir=${prefix}/share'",
                          runner.command_called)
        # opt-out from default installation dirs
        ab.configure(use_default_install_dirs=False)
        self.assertIn("--prefix=/package_folder", runner.command_called)
        self.assertNotIn("--bindir=${prefix}/bin", runner.command_called)
        self.assertNotIn("--libdir=${prefix}/lib", runner.command_called)
        self.assertNotIn("--includedir=${prefix}/lib", runner.command_called)

    def test_autotools_configure_vars(self):
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

    def test_autotools_fpic(self):
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

    def test_mac_version_min(self):
        options = MockOptions({})
        settings = MockSettings({"os": "Macos"})
        conanfile = MockConanfile(settings, options)
        be = AutoToolsBuildEnvironment(conanfile)
        expected = be.vars["CXXFLAGS"]
        self.assertNotIn("-mmacosx-version-min", expected)

        settings = MockSettings({"os": "Macos",
                                 "os.version": "10.13",
                                 "compiler.version": "12.0"})
        conanfile = MockConanfile(settings, options)
        be = AutoToolsBuildEnvironment(conanfile)
        expected = be.vars["CXXFLAGS"]
        self.assertIn("-mmacosx-version-min=10.13", expected)

        with tools.environment_append({"CFLAGS": "-mmacosx-version-min=10.9"}):
            be = AutoToolsBuildEnvironment(conanfile)
            expected = be.vars["CFLAGS"]
            self.assertIn("-mmacosx-version-min=10.9", expected)
            self.assertNotIn("-mmacosx-version-min=10.13", expected)

        with tools.environment_append({"CXXFLAGS": "-mmacosx-version-min=10.9"}):
            be = AutoToolsBuildEnvironment(conanfile)
            expected = be.vars["CFLAGS"]
            self.assertNotIn("-mmacosx-version-min=10.13", expected)
