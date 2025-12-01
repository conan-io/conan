import types

import pytest
from unittest.mock import Mock

from conan import ConanFile
from conan.internal.default_settings import default_settings_yml
from conan.tools.cmake import CMakeToolchain
from conan.tools.cmake.toolchain.blocks import Block
from conan.errors import ConanException
from conan.internal.model.conf import Conf
from conan.internal.model.options import Options
from conan.internal.model.settings import Settings


@pytest.fixture
def base_conanfile():
    c = ConanFile()
    settings = Settings.loads(default_settings_yml)
    c.settings = settings
    c.settings.build_type = "Release"
    c.settings.arch = "x86"
    c.settings.compiler = "clang"
    c.settings.compiler.libcxx = "libstdc++"
    c.settings_build = c.settings
    c.settings.os = "Windows"
    c.conf = Conf()
    c.folders.set_base_generators(".")  # non-existing to not relativize
    conan_node = Mock()
    conan_node.dependencies = []
    conan_node.transitive_deps = {}
    conan_node.replaced_requires = {}
    c._conan_node = conan_node
    return c


@pytest.fixture
def conanfile(base_conanfile):
    c = base_conanfile
    c.conf.define("tools.cmake.cmaketoolchain:system_name", "potato")
    return c


class TestGenericBlocks:
    """ Tests general toolchain blocks operations, enabling, disabling, customizing
    """
    def test_remove(self, conanfile):
        toolchain = CMakeToolchain(conanfile)
        toolchain.blocks.remove("generic_system")
        content = toolchain.content
        assert 'CMAKE_SYSTEM_NAME' not in content
        assert "CMAKE_CXX_FLAGS_INIT" in content
        assert "_CMAKE_IN_TRY_COMPILE" in content

        # remove multiple
        toolchain = CMakeToolchain(conanfile)
        toolchain.blocks.remove("generic_system", "cmake_flags_init")
        content = toolchain.content
        assert 'CMAKE_SYSTEM_NAME' not in content
        assert "CMAKE_CXX_FLAGS_INIT" not in content
        assert "_CMAKE_IN_TRY_COMPILE" in content

    def test_select_blocks(self, conanfile):
        toolchain = CMakeToolchain(conanfile)
        toolchain.blocks.select("generic_system")
        content = toolchain.content
        assert "########## 'generic_system' block #############" in content
        assert "########## 'cmake_flags_init' block #############" not in content
        assert "########## 'libcxx' block #############" not in content
        # These are not removed by default, to not break behavior
        assert "########## 'variables' block #############" in content
        assert "########## 'preprocessor' block #############" in content
        assert 'CMAKE_SYSTEM_NAME' in content
        assert "CMAKE_CXX_FLAGS_INIT" not in content
        assert "_CMAKE_IN_TRY_COMPILE" not in content

        # remove multiple
        toolchain = CMakeToolchain(conanfile)
        toolchain.blocks.select("generic_system", "cmake_flags_init")
        content = toolchain.content
        assert "########## 'generic_system' block #############" in content
        assert "########## 'cmake_flags_init' block #############" in content
        assert "########## 'libcxx' block #############" not in content
        # These are not removed by default, to not break behavior
        assert "########## 'variables' block #############" in content
        assert "########## 'preprocessor' block #############" in content
        assert 'CMAKE_SYSTEM_NAME' in content
        assert "CMAKE_CXX_FLAGS_INIT" in content
        assert "_CMAKE_IN_TRY_COMPILE" not in content

        # remove multiple
        toolchain = CMakeToolchain(conanfile)
        toolchain.blocks.enabled("generic_system")
        content = toolchain.content
        assert "########## 'generic_system' block #############" in content
        assert "########## 'variables' block #############" not in content
        assert "########## 'preprocessor' block #############" not in content

    def test_enabled_blocks_conf(self, conanfile):
        conanfile.conf.define("tools.cmake.cmaketoolchain:enabled_blocks", ["generic_system"])
        toolchain = CMakeToolchain(conanfile)
        content = toolchain.content
        assert "########## 'generic_system' block #############" in content
        assert "########## 'cmake_flags_init' block #############" not in content
        assert "########## 'libcxx' block #############" not in content
        assert "########## 'variables' block #############" not in content
        assert "########## 'preprocessor' block #############" not in content

        # remove multiple
        conanfile.conf.define("tools.cmake.cmaketoolchain:enabled_blocks",
                              ["generic_system", "cmake_flags_init"])
        toolchain = CMakeToolchain(conanfile)
        content = toolchain.content
        assert "########## 'generic_system' block #############" in content
        assert "########## 'cmake_flags_init' block #############" in content
        assert "########## 'libcxx' block #############" not in content
        assert "########## 'variables' block #############" not in content
        assert "########## 'preprocessor' block #############" not in content

        conanfile.conf.define("tools.cmake.cmaketoolchain:enabled_blocks", ["potato"])
        toolchain = CMakeToolchain(conanfile)
        with pytest.raises(ConanException) as e:
            _ = toolchain.content
        assert "Block 'potato' defined in tools.cmake.cmaketoolchain:enabled_blocks" in str(e)

    def test_dict_keys(self, conanfile):
        toolchain = CMakeToolchain(conanfile)
        assert "generic_system" in toolchain.blocks.keys()
        items = dict(toolchain.blocks.items())
        assert "generic_system" in items

    def test_template_remove(self, conanfile):
        toolchain = CMakeToolchain(conanfile)
        toolchain.blocks["generic_system"].template = ""
        content = toolchain.content
        assert 'CMAKE_SYSTEM_NAME' not in content

    def test_template_change(self, conanfile):
        toolchain = CMakeToolchain(conanfile)
        tmp = toolchain.blocks["generic_system"].template
        toolchain.blocks["generic_system"].template = tmp.replace("CMAKE_SYSTEM_NAME", "OTHER_THING")
        content = toolchain.content
        assert 'set(OTHER_THING potato)' in content

    def test_context_change(self, conanfile):
        toolchain = CMakeToolchain(conanfile)
        tmp = toolchain.blocks["generic_system"]

        def context(self_):
            assert self_
            return {"cmake_system_name": None}

        tmp.context = types.MethodType(context, tmp)
        content = toolchain.content
        assert 'CMAKE_SYSTEM_NAME' not in content

    def test_context_update(self, conanfile):
        toolchain = CMakeToolchain(conanfile)
        cmake_system_name = toolchain.blocks["generic_system"].values["cmake_system_name"]
        toolchain.blocks["generic_system"].values["cmake_system_name"] = "Super" + cmake_system_name
        content = toolchain.content
        assert 'set(CMAKE_SYSTEM_NAME Superpotato)' in content

    def test_context_replace(self, conanfile):
        toolchain = CMakeToolchain(conanfile)
        toolchain.blocks["generic_system"].values = {"cmake_system_name": "SuperPotato"}
        content = toolchain.content
        assert 'set(CMAKE_SYSTEM_NAME SuperPotato)' in content

    def test_replace_block(self, conanfile):
        toolchain = CMakeToolchain(conanfile)

        class MyBlock(Block):
            template = "HelloWorld"

            def context(self):
                return {}

        toolchain.blocks["generic_system"] = MyBlock
        content = toolchain.content
        assert 'HelloWorld' in content
        assert 'set(CMAKE_SYSTEM_NAME potato)' not in content

    def test_add_new_block(self, conanfile):
        toolchain = CMakeToolchain(conanfile)

        class MyBlock(Block):
            template = "Hello {{myvar}}!!!"

            def context(self):
                return {"myvar": "World"}

        toolchain.blocks["mynewblock"] = MyBlock
        content = toolchain.content
        assert 'Hello World!!!' in content
        assert 'set(CMAKE_SYSTEM_NAME potato)' in content

    def test_user_toolchain(self, conanfile):
        toolchain = CMakeToolchain(conanfile)
        toolchain.blocks["user_toolchain"].values["paths"] = ["myowntoolchain.cmake"]
        content = toolchain.content
        assert 'include("myowntoolchain.cmake")' in content


class TestBlocksFunctionality:
    def test_cmake_toolchain(self, conanfile):
        toolchain = CMakeToolchain(conanfile)
        content = toolchain.content
        assert 'set(CMAKE_SYSTEM_NAME potato)' in content

    def test_compilers_block(self, conanfile):
        cmake_mapping = {"c": "C", "cuda": "CUDA", "cpp": "CXX", "objc": "OBJC",
                         "objcpp": "OBJCXX", "rc": "RC", 'fortran': "Fortran", 'asm': "ASM",
                         "hip": "HIP", "ispc": "ISPC"}
        compilers = {"c": "path_to_c", "cuda": "path_to_cuda", "cpp": "path_to_cpp",
                     "objc": "path_to_objc", "objcpp": "path_to_objcpp", "rc": "path_to_rc",
                     'fortran': "path_to_fortran", 'asm': "path_to_asm", "hip": "path_to_hip",
                     "ispc": "path_to_ispc"}
        conanfile.conf.define("tools.build:compiler_executables", compilers)
        toolchain = CMakeToolchain(conanfile)
        content = toolchain.content
        for compiler, lang in cmake_mapping.items():
            assert f'set(CMAKE_{lang}_COMPILER "path_to_{compiler}")' in content

    def test_linker_scripts_block(self, conanfile):
        conanfile.conf.define("tools.build:linker_scripts",
                              ["path_to_first_linker_script", "path_to_second_linker_script"])
        toolchain = CMakeToolchain(conanfile)
        content = toolchain.content
        assert r'string(APPEND CONAN_EXE_LINKER_FLAGS " -T\"path_to_first_linker_script\" ' \
               r'-T\"path_to_second_linker_script\"")' in content

    def test_libcxx_abi_flag(self, base_conanfile):
        c = base_conanfile
        c.settings.build_type = "Release"
        c.settings.arch = "x86_64"
        c.settings.compiler = "gcc"
        c.settings.compiler.version = "11"
        c.settings.compiler.cppstd = "20"
        c.settings.compiler.libcxx = "libstdc++"
        c.settings.os = "Linux"

        toolchain = CMakeToolchain(c)
        content = toolchain.content
        assert '_GLIBCXX_USE_CXX11_ABI=0' in content
        c.settings.compiler.libcxx = "libstdc++11"
        toolchain = CMakeToolchain(c)
        content = toolchain.content
        # by default, no flag is output anymore, it is assumed the compiler default
        assert 'GLIBCXX_USE_CXX11_ABI' not in content
        # recipe workaround for older distros
        toolchain.blocks["libcxx"].values["glibcxx"] = "_GLIBCXX_USE_CXX11_ABI=1"
        content = toolchain.content
        assert '_GLIBCXX_USE_CXX11_ABI=1' in content

        # but maybe the conf is better
        c.conf.define("tools.gnu:define_libcxx11_abi", True)
        toolchain = CMakeToolchain(c)
        content = toolchain.content
        assert '_GLIBCXX_USE_CXX11_ABI=1' in content


class TestMSVCToolset:
    @pytest.fixture
    def conanfile_msvc(self, base_conanfile):
        c = base_conanfile
        c.settings.build_type = "Release"
        c.settings.arch = "x86"
        c.settings.compiler = "msvc"
        c.settings.compiler.version = "194"
        c.settings.compiler.cppstd = "20"
        c.settings.os = "Windows"
        return c

    def test_toolset(self, conanfile_msvc):
        toolchain = CMakeToolchain(conanfile_msvc)
        assert 'set(CMAKE_GENERATOR_TOOLSET "v143" CACHE STRING "" FORCE)' in toolchain.content
        assert 'Visual Studio 17 2022' in toolchain.generator
        assert 'CMAKE_CXX_STANDARD 20' in toolchain.content

    def test_toolset_latest_generator(self, conanfile_msvc):
        conanfile_msvc.settings.compiler.version = "195"
        toolchain = CMakeToolchain(conanfile_msvc)
        assert 'set(CMAKE_GENERATOR_TOOLSET "v145" CACHE STRING "" FORCE)' in toolchain.content
        assert 'Visual Studio 18 2026' in toolchain.generator

    def test_toolset_update_version(self, conanfile_msvc):
        conanfile_msvc.settings.compiler.version = "193"
        conanfile_msvc.settings.compiler.update = "8"
        c = CMakeToolchain(conanfile_msvc)
        assert 'set(CMAKE_GENERATOR_TOOLSET "v143,version=14.38" CACHE STRING "" FORCE)' in c.content

    def test_toolset_update_version_conf(self, conanfile_msvc):
        conanfile_msvc.settings.compiler.version = "193"
        conanfile_msvc.conf.define("tools.microsoft:msvc_update", "7")
        c = CMakeToolchain(conanfile_msvc)
        assert 'set(CMAKE_GENERATOR_TOOLSET "v143,version=14.37" CACHE STRING "" FORCE)' in c.content

    def test_toolset_update_version_forced_conf(self, conanfile_msvc):
        conanfile_msvc.settings.compiler.version = "193"
        conanfile_msvc.settings.compiler.update = "8"
        conanfile_msvc.conf.define("tools.microsoft:msvc_update", "7")
        c = CMakeToolchain(conanfile_msvc)
        assert 'set(CMAKE_GENERATOR_TOOLSET "v143,version=14.37" CACHE STRING "" FORCE)' in c.content

    def test_toolset_update_version_overflow(self, conanfile_msvc):
        # https://github.com/conan-io/conan/issues/15583
        conanfile_msvc.settings.compiler.version = "194"
        conanfile_msvc.settings.compiler.update = "8"
        c = CMakeToolchain(conanfile_msvc)
        assert 'set(CMAKE_GENERATOR_TOOLSET "v143,version=14.48" CACHE STRING "" FORCE)' in c.content

    def test_toolset_x64(self, conanfile_msvc):
        # https://github.com/conan-io/conan/issues/11144
        conanfile_msvc.conf.define("tools.cmake.cmaketoolchain:toolset_arch", "x64")
        c = CMakeToolchain(conanfile_msvc)
        assert 'set(CMAKE_GENERATOR_TOOLSET "v143,host=x64" CACHE STRING "" FORCE)' in c.content
        assert 'Visual Studio 17 2022' in c.generator
        assert 'CMAKE_CXX_STANDARD 20' in c.content

    def test_toolset_cuda(self, conanfile_msvc):
        conanfile_msvc.conf.define("tools.cmake.cmaketoolchain:toolset_cuda", "C:/Path/To/CUDA")
        c = CMakeToolchain(conanfile_msvc)
        assert ('set(CMAKE_GENERATOR_TOOLSET "v143,cuda=C:/Path/To/CUDA" '
                'CACHE STRING "" FORCE)') in c.content

    def test_older_msvc_toolset(self, conanfile_msvc):
        c = conanfile_msvc
        c.settings.compiler.version = "170"
        c.settings.compiler.cppstd = "14"
        toolchain = CMakeToolchain(c)
        content = toolchain.content
        assert 'CMAKE_GENERATOR_TOOLSET "v110"' in content
        # As by the CMake docs, this has no effect for VS < 2015
        assert 'CMAKE_CXX_STANDARD 14' in content

    def test_vs_clangcl(self, conanfile_msvc):
        c = conanfile_msvc
        c.settings.build_type = "Release"
        c.settings.arch = "x86_64"
        c.settings.compiler = "clang"
        c.settings.compiler.runtime_version = "v145"
        c.settings.compiler.version = "20"
        c.settings.compiler.cppstd = "14"
        c.settings.os = "Windows"
        c.conf.define("tools.cmake.cmaketoolchain:generator", "Visual Studio 18")
        toolchain = CMakeToolchain(c)
        content = toolchain.content
        assert 'CMAKE_GENERATOR_TOOLSET "ClangCL"' in content
        assert 'CMAKE_CXX_STANDARD 14' in content

    def test_older_msvc_toolset_update(self, conanfile_msvc):
        # https://github.com/conan-io/conan/issues/15787
        c = conanfile_msvc
        c.settings.arch = "x86_64"
        c.settings.compiler = "msvc"
        c.settings.compiler.version = "192"
        c.settings.compiler.update = "9"
        c.settings.compiler.cppstd = "14"
        c.settings.os = "Windows"
        toolchain = CMakeToolchain(c)
        content = toolchain.content
        assert 'CMAKE_GENERATOR_TOOLSET "v142,version=14.29"' in content

    def test_msvc_xp_toolsets(self, conanfile_msvc):
        c = conanfile_msvc
        c.settings.build_type = "Release"
        c.settings.arch = "x86"
        c.settings.compiler = "msvc"
        c.settings.compiler.version = "170"
        c.settings.compiler.toolset = "v110_xp"
        c.settings.compiler.cppstd = "14"
        toolchain = CMakeToolchain(c)
        content = toolchain.content
        assert 'CMAKE_GENERATOR_TOOLSET "v110_xp"' in content
        # As by the CMake docs, this has no effect for VS < 2015
        assert 'CMAKE_CXX_STANDARD 14' in content


class TestFpic:
    @pytest.fixture
    def conanfile_linux(self, base_conanfile):
        c = base_conanfile
        c.settings.build_type = "Release"
        c.settings.arch = "x86_64"
        c.settings.compiler = "gcc"
        c.settings.compiler.version = "11"
        c.settings.compiler.cppstd = "20"
        c.settings.os = "Linux"
        return c

    def test_no_fpic_when_not_an_option(self, conanfile_linux):
        toolchain = CMakeToolchain(conanfile_linux)
        content = toolchain.content
        assert 'set(CMAKE_POSITION_INDEPENDENT_CODE' not in content

    @pytest.fixture
    def conanfile_linux_shared(self, conanfile_linux):
        c = conanfile_linux
        c.options = Options({"fPIC": [True, False],
                             "shared": [True, False]},
                            {"fPIC": False, "shared": True, })
        return c

    @pytest.mark.parametrize("fpic", [True, False])
    def test_fpic_when_shared_true(self, conanfile_linux_shared, fpic):
        conanfile_linux_shared.options.fPIC = fpic
        toolchain = CMakeToolchain(conanfile_linux_shared)
        cmake_value = 'ON' if fpic else 'OFF'
        content = toolchain.content
        assert 'set(CMAKE_POSITION_INDEPENDENT_CODE {} CACHE BOOL'.format(cmake_value) in content

    def test_fpic_when_not_shared(self, conanfile_linux_shared):
        conanfile_linux_shared.options.shared = False
        toolchain = CMakeToolchain(conanfile_linux_shared)
        content = toolchain.content
        assert 'set(CMAKE_POSITION_INDEPENDENT_CODE' in content

    @pytest.fixture
    def conanfile_windows_fpic(self, base_conanfile):
        c = base_conanfile
        c.options = Options({"fPIC": [True, False]},
                            {"fPIC": True})
        c.settings.build_type = "Release"
        c.settings.arch = "x86"
        c.settings.compiler = "gcc"
        c.settings.compiler.libcxx = "libstdc++"
        c.settings.os = "Windows"
        return c

    def test_no_fpic_on_windows(self, conanfile_windows_fpic):
        toolchain = CMakeToolchain(conanfile_windows_fpic)
        content = toolchain.content
        assert 'set(CMAKE_POSITION_INDEPENDENT_CODE' not in content

    @pytest.fixture
    def conanfile_linux_fpic(self, base_conanfile):
        c = base_conanfile
        c.options = Options({"fPIC": [True, False]},
                            {"fPIC": False})
        c.settings.build_type = "Release"
        c.settings.arch = "x86_64"
        c.settings.compiler = "gcc"
        c.settings.compiler.version = "11"
        c.settings.compiler.cppstd = "20"
        c.settings.os = "Linux"
        return c

    def test_fpic_disabled(self, conanfile_linux_fpic):
        conanfile_linux_fpic.options.fPIC = False
        toolchain = CMakeToolchain(conanfile_linux_fpic)
        content = toolchain.content
        assert 'set(CMAKE_POSITION_INDEPENDENT_CODE OFF' in content

    def test_fpic_enabled(self, conanfile_linux_fpic):
        conanfile_linux_fpic.options.fPIC = True
        toolchain = CMakeToolchain(conanfile_linux_fpic)
        content = toolchain.content
        assert 'set(CMAKE_POSITION_INDEPENDENT_CODE ON' in content


class TestApple:
    def test_osx_deployment_target(self, base_conanfile):
        c = base_conanfile
        c.settings.build_type = "Release"
        c.settings.arch = "x86"
        c.settings.compiler = "apple-clang"
        c.settings.compiler.libcxx = "libc++"
        c.settings.os = "Macos"
        c.settings.os.version = "10.15"
        toolchain = CMakeToolchain(c)
        content = toolchain.content
        assert 'set(CMAKE_OSX_DEPLOYMENT_TARGET "10.15" CACHE STRING "")' in content

    @pytest.mark.parametrize("os,os_sdk,arch,expected_sdk", [
        ("Macos", None, "x86_64", "macosx"),
        ("Macos", None, "armv7", "macosx"),
        ("iOS", "iphonesimulator", "armv8", "iphonesimulator"),
        ("watchOS", "watchsimulator", "armv8", "watchsimulator")
    ])
    def test_apple_cmake_osx_sysroot(self, base_conanfile, os, os_sdk, arch, expected_sdk):
        """
        Testing if CMAKE_OSX_SYSROOT is correctly set.
        Issue related: https://github.com/conan-io/conan/issues/10275
        """
        c = base_conanfile
        c.settings.os = os
        if os_sdk:
            c.settings.os.sdk = os_sdk
        c.settings.build_type = "Release"
        c.settings.arch = arch
        c.settings.compiler = "apple-clang"
        c.settings.compiler.version = "13.0"
        c.settings.compiler.libcxx = "libc++"
        c.settings.compiler.cppstd = "17"

        toolchain = CMakeToolchain(c)
        content = toolchain.content
        assert 'set(CMAKE_OSX_SYSROOT %s CACHE STRING "" FORCE)' % expected_sdk in content

    @pytest.mark.parametrize("os,arch,expected_sdk", [
        ("iOS", "x86_64", ""),
        ("watchOS", "armv8", ""),
        ("tvOS", "x86_64", "")
    ])
    def test_apple_cmake_osx_sysroot_sdk_mandatory(self, base_conanfile, os, arch, expected_sdk):
        """
        Testing if CMAKE_OSX_SYSROOT is correctly set.
        Issue related: https://github.com/conan-io/conan/issues/10275
        """
        c = base_conanfile
        c.settings.os = os
        c.settings.build_type = "Release"
        c.settings.arch = arch
        c.settings.compiler = "apple-clang"
        c.settings.compiler.version = "13.0"
        c.settings.compiler.libcxx = "libc++"
        c.settings.compiler.cppstd = "17"

        with pytest.raises(ConanException) as excinfo:
            _ = CMakeToolchain(c).content
        assert "Please, specify a suitable value for os.sdk." in str(excinfo.value)


class TestCrossBuild:
    @pytest.fixture
    def conanfile_cross(self, base_conanfile):
        c = base_conanfile
        c.settings.build_type = "Release"
        c.settings.arch = "armv8"
        c.settings.compiler = "gcc"
        c.settings.compiler.version = "11"
        c.settings.compiler.cppstd = "20"
        c.settings.os = "baremetal"
        c.settings_build = c.settings.copy()
        c.settings_build.os = "Linux"
        c.settings_build.arch = "x86_64"
        return c

    def test_cmake_system_name(self, conanfile_cross):
        toolchain = CMakeToolchain(conanfile_cross)
        content = toolchain.content
        assert 'set(CMAKE_SYSTEM_NAME Generic)' in content
