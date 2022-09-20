import unittest

from conans.client.conf import get_default_settings_yml
from conans.client.generators.compiler_args import CompilerArgsGenerator
from conans.client.generators.gcc import GCCGenerator
from conans.model.build_info import CppInfo, DepsCppInfo
from conans.model.env_info import DepsEnvInfo, EnvInfo
from conans.model.settings import Settings
from conans.model.user_info import DepsUserInfo
from conans.test.utils.mocks import ConanFileMock


class CompilerArgsTest(unittest.TestCase):

    def test_visual_studio_extensions(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.build_type = "Release"

        conan_file = ConanFileMock()
        conan_file.settings = settings
        conan_file.deps_env_info = DepsEnvInfo()
        conan_file.deps_user_info = DepsUserInfo()
        conan_file.deps_cpp_info = DepsCppInfo()
        cpp_info = CppInfo("zlib", "/root")
        cpp_info.libs.append("mylib")
        cpp_info.libs.append("other.lib")
        conan_file.deps_cpp_info.add("zlib", cpp_info)
        conan_file.env_info = EnvInfo()

        gen = CompilerArgsGenerator(conan_file)
        self.assertEqual('-O2 -Ob2 -DNDEBUG -link mylib.lib other.lib', gen.content)

    @staticmethod
    def _get_conanfile(settings, frameworks=False, system_libs=False):
        conan_file = ConanFileMock()
        conan_file.settings = settings
        conan_file.folders.set_base_source("my_cache_source_folder")
        conan_file.folders.set_base_build("my_cache_build_folder")
        conan_file.deps_env_info = DepsEnvInfo()
        conan_file.deps_user_info = DepsUserInfo()
        conan_file.deps_cpp_info = DepsCppInfo()

        cpp_info = CppInfo("zlib", "/root")
        cpp_info.includedirs.append("path/to/include1")
        cpp_info.libdirs.append("path/to/lib1")
        cpp_info.libs.append("mylib")
        cpp_info.bindirs = "path/to/bin1"
        cpp_info.cflags.append("c_flag1")
        cpp_info.cxxflags.append("cxx_flag1")
        cpp_info.defines.append("mydefine1")
        if system_libs:
            cpp_info.system_libs.append("system_lib1")
        if frameworks:
            cpp_info.frameworks = ["AVFoundation", "VideoToolbox"]
            cpp_info.frameworkdirs.extend(['path/to/Frameworks1', 'path/to/Frameworks2'])
        cpp_info.filter_empty = False
        conan_file.deps_cpp_info.add("zlib", cpp_info)

        conan_file.env_info = EnvInfo()
        return conan_file

    def test_gcc(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Linux"
        settings.compiler = "gcc"
        settings.compiler.version = "6.3"
        settings.arch = "x86"
        settings.build_type = "Release"
        settings.cppstd = "gnu17"

        conan_file = self._get_conanfile(settings)
        gcc = GCCGenerator(conan_file)
        self.assertEqual('-Dmydefine1 -I/root/include -I/root/path/to/include1'
                         ' cxx_flag1 c_flag1 -m32 -O3 -s -DNDEBUG'
                         ' -Wl,-rpath,"/root/lib" -Wl,-rpath,"/root/path/to/lib1"'
                         ' -L/root/lib -L/root/path/to/lib1 -lmylib'
                         ' -F /root/Frameworks -std=gnu++17', gcc.content)

        settings.arch = "x86_64"
        settings.build_type = "Debug"
        settings.compiler.libcxx = "libstdc++11"

        gcc = GCCGenerator(conan_file)
        self.assertEqual('-Dmydefine1 -I/root/include -I/root/path/to/include1'
                         ' cxx_flag1 c_flag1 -m64 -g'
                         ' -Wl,-rpath,"/root/lib" -Wl,-rpath,"/root/path/to/lib1"'
                         ' -L/root/lib -L/root/path/to/lib1 -lmylib'
                         ' -D_GLIBCXX_USE_CXX11_ABI=1 -F /root/Frameworks -std=gnu++17',
                         gcc.content)

        settings.compiler.libcxx = "libstdc++"
        gcc = GCCGenerator(conan_file)
        self.assertEqual('-Dmydefine1 -I/root/include -I/root/path/to/include1'
                         ' cxx_flag1 c_flag1 -m64 -g'
                         ' -Wl,-rpath,"/root/lib" -Wl,-rpath,"/root/path/to/lib1"'
                         ' -L/root/lib -L/root/path/to/lib1 -lmylib'
                         ' -D_GLIBCXX_USE_CXX11_ABI=0 -F /root/Frameworks -std=gnu++17',
                         gcc.content)

        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.build_type = "Release"
        gcc = GCCGenerator(conan_file)
        # GCC generator ignores the compiler setting, it is always gcc
        self.assertEqual('-Dmydefine1 -I/root/include -I/root/path/to/include1'
                         ' cxx_flag1 c_flag1 -m32 -O3 -s -DNDEBUG'
                         ' -Wl,-rpath,"/root/lib" -Wl,-rpath,"/root/path/to/lib1"'
                         ' -L/root/lib -L/root/path/to/lib1 -lmylib'
                         ' -D_GLIBCXX_USE_CXX11_ABI=0 -F /root/Frameworks -std=gnu++17',
                         gcc.content)

    def test_compiler_args(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.build_type = "Release"

        conan_file = self._get_conanfile(settings)
        gen = CompilerArgsGenerator(conan_file)
        self.assertEqual('-Dmydefine1 -I\\root\\include -I\\root\\path\\to\\include1'
                         ' cxx_flag1 c_flag1 -O2 -Ob2 -DNDEBUG -link'
                         ' -LIBPATH:\\root\\lib -LIBPATH:\\root\\path\\to\\lib1 mylib.lib',
                         gen.content)

        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Macos"
        settings.compiler = "apple-clang"
        settings.compiler.version = "9.0"
        settings.arch = "x86"
        settings.build_type = "Release"
        conan_file = self._get_conanfile(settings)
        gen = CompilerArgsGenerator(conan_file)
        self.assertEqual('-Dmydefine1 -I/root/include -I/root/path/to/include1'
                         ' cxx_flag1 c_flag1 -m32 -O3 -DNDEBUG'
                         ' -Wl,-rpath,"/root/lib" -Wl,-rpath,"/root/path/to/lib1"'
                         ' -L/root/lib -L/root/path/to/lib1 -lmylib'
                         ' -F /root/Frameworks', gen.content)

        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Linux"
        settings.os_build = "Macos"
        settings.compiler = "apple-clang"
        settings.compiler.version = "9.0"
        settings.arch = "x86"
        settings.build_type = "Release"

        conan_file = self._get_conanfile(settings)
        args = CompilerArgsGenerator(conan_file)
        self.assertEqual('-Dmydefine1 -I/root/include -I/root/path/to/include1'
                         ' cxx_flag1 c_flag1 -m32 -O3 -DNDEBUG'
                         ' -Wl,-rpath,"/root/lib" -Wl,-rpath,"/root/path/to/lib1"'
                         ' -L/root/lib -L/root/path/to/lib1 -lmylib'
                         ' -F /root/Frameworks', args.content)

    def test_apple_frameworks(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Macos"
        settings.compiler = "apple-clang"
        settings.compiler.version = "9.1"
        settings.arch = "x86_64"
        settings.build_type = "Release"

        conan_file = self._get_conanfile(settings, frameworks=True)
        args = CompilerArgsGenerator(conan_file)
        self.assertEqual('-Dmydefine1 -I/root/include -I/root/path/to/include1'
                         ' cxx_flag1 c_flag1 -m64 -O3 -DNDEBUG'
                         ' -Wl,-rpath,"/root/lib" -Wl,-rpath,"/root/path/to/lib1"'
                         ' -L/root/lib -L/root/path/to/lib1 -lmylib'
                         ' -framework AVFoundation -framework VideoToolbox'
                         ' -F /root/Frameworks -F /root/path/to/Frameworks1'
                         ' -F /root/path/to/Frameworks2', args.content)

    def test_system_libs(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Linux"
        settings.compiler = "gcc"
        settings.compiler.version = "8"
        settings.arch = "x86_64"
        settings.build_type = "Release"

        conan_file = self._get_conanfile(settings, system_libs=True)
        args = CompilerArgsGenerator(conan_file)
        self.assertEqual('-Dmydefine1 -I/root/include -I/root/path/to/include1'
                         ' cxx_flag1 c_flag1 -m64 -O3 -s -DNDEBUG'
                         ' -Wl,-rpath,"/root/lib" -Wl,-rpath,"/root/path/to/lib1"'
                         ' -L/root/lib -L/root/path/to/lib1 -lmylib -lsystem_lib1'
                         ' -F /root/Frameworks', args.content)
