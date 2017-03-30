import unittest

from conans.client.configure_build_environment import AutoToolsBuildEnvironment


class MockDepsCppInfo(object):

    def __init__(self):
        self.include_paths = []
        self.lib_paths = []
        self.libs = []
        self.defines = []
        self.cflags = []
        self.cppflags = []
        self.sharedlinkflags = []
        self.exelinkflags = []


class MockConanfile(object):

    def __init__(self, settings):
        self.deps_cpp_info = MockDepsCppInfo()
        self.settings = settings


class MockSettings(object):

    def __init__(self, values):
        self.values = values

    def get_safe(self, value):
        return self.values.get(value, None)


class AutoToolsConfigureTest(unittest.TestCase):

    def _set_deps_info(self, conanfile):
        conanfile.deps_cpp_info.include_paths.append("path/includes")
        conanfile.deps_cpp_info.include_paths.append("other/include/path")
        conanfile.deps_cpp_info.lib_paths.append("one/lib/path")
        conanfile.deps_cpp_info.libs.append("onelib")
        conanfile.deps_cpp_info.libs.append("twolib")
        conanfile.deps_cpp_info.defines.append("onedefinition")
        conanfile.deps_cpp_info.defines.append("twodefinition")
        conanfile.deps_cpp_info.cflags.append("a_c_flag")
        conanfile.deps_cpp_info.cppflags.append("a_cpp_flag")
        conanfile.deps_cpp_info.sharedlinkflags.append("shared_link_flag")
        conanfile.deps_cpp_info.exelinkflags.append("exe_link_flag")

    def test_variables(self):
        # GCC 32
        settings = MockSettings({"build_type": "Release",
                                 "arch": "x86",
                                 "compiler": "gcc",
                                 "compiler.libcxx": "libstdc++"})
        conanfile = MockConanfile(settings)
        self._set_deps_info(conanfile)

        be = AutoToolsBuildEnvironment(conanfile)
        expected = {'CFLAGS': 'a_c_flag -m32 -s',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition -DNDEBUG '
                                '-D_GLIBCXX_USE_CXX11_ABI=0',
                    'CXXFLAGS': 'a_c_flag -m32 -s a_cpp_flag',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m32 -Lone/lib/path',
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
        expected = {'CFLAGS': 'a_c_flag -m64 -g',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition'
                                ' -D_GLIBCXX_USE_CXX11_ABI=0',
                    'CXXFLAGS': 'a_c_flag -m64 -g a_cpp_flag',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 -Lone/lib/path',
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
        expected = {'CFLAGS': 'a_c_flag -m64',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition'
                                ' -D_GLIBCXX_USE_CXX11_ABI=0',
                    'CXXFLAGS': 'a_c_flag -m64 a_cpp_flag -stdlib=libstdc++',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 -Lone/lib/path',
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
        expected = {'CFLAGS': 'a_c_flag -m64',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition',
                    'CXXFLAGS': 'a_c_flag -m64 a_cpp_flag -stdlib=libc++',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 -Lone/lib/path',
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
        expected = {'CFLAGS': 'a_c_flag -m64 -s',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition -DNDEBUG '
                                '-D_GLIBCXX_USE_CXX11_ABI=1',
                    'CXXFLAGS': 'a_c_flag -m64 -s a_cpp_flag',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 -Lone/lib/path',
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
        expected = {'CFLAGS': 'a_c_flag -m64',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition',
                    'CXXFLAGS': 'a_c_flag -m64 a_cpp_flag -library=Cstd',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 -Lone/lib/path',
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
        expected = {'CFLAGS': 'a_c_flag -m64',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition',
                    'CXXFLAGS': 'a_c_flag -m64 a_cpp_flag -library=stdcxx4',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 -Lone/lib/path',
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
        expected = {'CFLAGS': 'a_c_flag -m64',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition',
                    'CXXFLAGS': 'a_c_flag -m64 a_cpp_flag -library=stlport4',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 -Lone/lib/path',
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
        expected = {'CFLAGS': 'a_c_flag -m64',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition',
                    'CXXFLAGS': 'a_c_flag -m64 a_cpp_flag -library=stdcpp',
                    'LDFLAGS': 'shared_link_flag exe_link_flag -m64 -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib'}
        be = AutoToolsBuildEnvironment(conanfile)
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

        expected = {'CFLAGS': 'a_c_flag -m64 -g cucucu -fPIC',
                    'CPPFLAGS': '-Ipath/includes -Iother/include/path -Donedefinition -Dtwodefinition'
                                ' -D_GLIBCXX_USE_CXX11_ABI=0 -DOtherDefinition=23',
                    'CXXFLAGS': 'a_c_flag -m64 -g cucucu -fPIC a_cpp_flag -onlycxx',
                    'LDFLAGS': '-inventedflag -Lone/lib/path',
                    'LIBS': '-lonelib -ltwolib'}
        self.assertEquals(be.vars, expected)

    def cross_build_flags_test(self):
        def get_values(this_os, this_arch, setting_os, setting_arch):
            settings = MockSettings({"arch": setting_arch,
                                     "os": setting_os})
            conanfile = MockConanfile(settings)
            conanfile.settings = settings
            be = AutoToolsBuildEnvironment(conanfile)
            return be._get_host_build_target_flags(this_arch, this_os)

        build, host, target = get_values("Linux", "x86_64", "Linux", "armv7hf")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "arm-linux-gnueabihf")

        build, host, target = get_values("Linux", "x86", "Linux", "armv7hf")
        self.assertEquals(build, "x86-linux-gnu")
        self.assertEquals(host, "arm-linux-gnueabihf")

        build, host, target = get_values("Linux", "x86", "Linux", "x86")
        self.assertIsNone(build)
        self.assertIsNone(host)
        self.assertIsNone(target)

        build, host, target = get_values("Linux", "x86_64", "Linux", "x86_64")
        self.assertIsNone(build)
        self.assertIsNone(host)
        self.assertIsNone(target)

        build, host, target = get_values("Linux", "x86_64", "Linux", "x86")
        self.assertIsNone(build)
        self.assertIsNone(host)
        self.assertIsNone(target)

        build, host, target = get_values("Linux", "x86_64", "Linux", "armv7hf")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "arm-linux-gnueabihf")

        build, host, target = get_values("Linux", "x86_64", "Linux", "armv7")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "arm-linux-gnueabi")

        build, host, target = get_values("Linux", "x86_64", "Linux", "armv6")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "arm-linux-gnueabi")

        build, host, target = get_values("Linux", "x86_64", "Android", "x86")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "x86-linux-android")

        build, host, target = get_values("Linux", "x86_64", "Android", "x86_64")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "x86_64-linux-android")

        build, host, target = get_values("Linux", "x86_64", "Android", "armv7")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "arm-linux-androideabi")

        build, host, target = get_values("Linux", "x86_64", "Android", "armv7hf")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "arm-linux-androideabi")

        build, host, target = get_values("Linux", "x86_64", "Android", "armv8")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "aarch64-linux-android")

        build, host, target = get_values("Linux", "x86_64", "Android", "armv6")
        self.assertEquals(build, "x86_64-linux-gnu")
        self.assertEquals(host, "arm-linux-androideabi")

        build, host, target = get_values("Linux", "x86_64", "Windows", "x86")
        self.assertEquals(build, "x86_64-w64-mingw32")
        self.assertEquals(host, "i686-w64-mingw32")

        build, host, target = get_values("Linux", "x86_64", "Windows", "x86_64")
        self.assertEquals(build, "x86_64-w64-mingw32")
        self.assertEquals(host, "x86_64-w64-mingw32")

        build, host, target = get_values("Windows", "x86_64", "Windows", "x86_64")
        self.assertIsNone(build)
        self.assertIsNone(host)
        self.assertIsNone(target)

        build, host, target = get_values("Windows", "x86", "Windows", "x86")
        self.assertIsNone(build)
        self.assertIsNone(host)
        self.assertIsNone(target)

        build, host, target = get_values("Windows", "x86_64", "Windows", "x86")
        self.assertIsNone(build)
        self.assertIsNone(host)
        self.assertIsNone(target)

        build, host, target = get_values("Windows", "x86_64", "Linux", "armv7hf")
        self.assertIsNone(build)
        self.assertIsNone(host)
        self.assertIsNone(target)

        build, host, target = get_values("Windows", "x86_64", "Linux", "x86_64")
        self.assertIsNone(build)
        self.assertIsNone(host)
        self.assertIsNone(target)

        build, host, target = get_values("Darwin", "x86_64", "Android", "armv7hf")
        self.assertEquals(build, "x86_64-apple-macos")
        self.assertEquals(host, "arm-linux-androideabi")