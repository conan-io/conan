import os
import types

import pytest
from mock import Mock

from conan.tools.cmake import CMakeToolchain
from conan import ConanFile
from conan.tools.cmake.toolchain.blocks import Block
from conans.client.conf import get_default_settings_yml
from conans.errors import ConanException
from conans.model.conf import Conf
from conans.model.options import Options
from conans.model.settings import Settings
from conans.test.utils.test_files import temp_folder
from conans.util.files import load


@pytest.fixture
def conanfile():
    c = ConanFile()
    settings = Settings({"os": ["Windows"],
                           "compiler": {"clang": {"libcxx": ["libstdc++"]}},
                           "build_type": ["Release"],
                           "arch": ["x86"]})
    c.settings = settings
    c.settings.build_type = "Release"
    c.settings.arch = "x86"
    c.settings.compiler = "clang"
    c.settings.compiler.libcxx = "libstdc++"
    c.settings_build = c.settings
    c.settings.os = "Windows"
    c.conf = Conf()
    c.conf.define("tools.cmake.cmaketoolchain:system_name", "potato")
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.transitive_deps = {}
    return c


def test_cmake_toolchain(conanfile):
    toolchain = CMakeToolchain(conanfile)
    content = toolchain.content
    assert 'set(CMAKE_SYSTEM_NAME potato)' in content


def test_remove(conanfile):
    toolchain = CMakeToolchain(conanfile)
    toolchain.blocks.remove("generic_system")
    content = toolchain.content
    assert 'CMAKE_SYSTEM_NAME' not in content


def test_template_remove(conanfile):
    toolchain = CMakeToolchain(conanfile)
    toolchain.blocks["generic_system"].template = ""
    content = toolchain.content
    assert 'CMAKE_SYSTEM_NAME' not in content


def test_template_change(conanfile):
    toolchain = CMakeToolchain(conanfile)
    tmp = toolchain.blocks["generic_system"].template
    toolchain.blocks["generic_system"].template = tmp.replace("CMAKE_SYSTEM_NAME", "OTHER_THING")
    content = toolchain.content
    assert 'set(OTHER_THING potato)' in content


def test_context_change(conanfile):
    toolchain = CMakeToolchain(conanfile)
    tmp = toolchain.blocks["generic_system"]

    def context(self):
        assert self
        return {"cmake_system_name": None}

    tmp.context = types.MethodType(context, tmp)
    content = toolchain.content
    assert 'CMAKE_SYSTEM_NAME' not in content


def test_context_update(conanfile):
    toolchain = CMakeToolchain(conanfile)
    cmake_system_name = toolchain.blocks["generic_system"].values["cmake_system_name"]
    toolchain.blocks["generic_system"].values["cmake_system_name"] = "Super" + cmake_system_name
    content = toolchain.content
    assert 'set(CMAKE_SYSTEM_NAME Superpotato)' in content


def test_context_replace(conanfile):
    toolchain = CMakeToolchain(conanfile)
    toolchain.blocks["generic_system"].values = {"cmake_system_name": "SuperPotato"}
    content = toolchain.content
    assert 'set(CMAKE_SYSTEM_NAME SuperPotato)' in content


def test_replace_block(conanfile):
    toolchain = CMakeToolchain(conanfile)

    class MyBlock(Block):
        template = "HelloWorld"

        def context(self):
            return {}

    toolchain.blocks["generic_system"] = MyBlock
    content = toolchain.content
    assert 'HelloWorld' in content
    assert 'set(CMAKE_SYSTEM_NAME potato)' not in content


def test_add_new_block(conanfile):
    toolchain = CMakeToolchain(conanfile)

    class MyBlock(Block):
        template = "Hello {{myvar}}!!!"

        def context(self):
            return {"myvar": "World"}

    toolchain.blocks["mynewblock"] = MyBlock
    content = toolchain.content
    assert 'Hello World!!!' in content
    assert 'set(CMAKE_SYSTEM_NAME potato)' in content


def test_user_toolchain(conanfile):
    toolchain = CMakeToolchain(conanfile)
    toolchain.blocks["user_toolchain"].values["paths"] = ["myowntoolchain.cmake"]
    content = toolchain.content
    assert 'include("myowntoolchain.cmake")' in content


@pytest.fixture
def conanfile_apple():
    c = ConanFile(None)
    c.settings = Settings({"os": {"Macos": {"version": ["10.15"]}},
                           "compiler": {"apple-clang": {"libcxx": ["libc++"]}},
                           "build_type": ["Release"],
                           "arch": ["x86"]})
    c.settings.build_type = "Release"
    c.settings.arch = "x86"
    c.settings.compiler = "apple-clang"
    c.settings.compiler.libcxx = "libc++"
    c.settings.os = "Macos"
    c.settings.os.version = "10.15"
    c.settings_build = c.settings
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    c._conan_node.transitive_deps = {}
    return c


def test_osx_deployment_target(conanfile_apple):
    toolchain = CMakeToolchain(conanfile_apple)
    content = toolchain.content
    assert 'set(CMAKE_OSX_DEPLOYMENT_TARGET "10.15" CACHE STRING "")' in content


@pytest.fixture
def conanfile_msvc():
    c = ConanFile(None)
    c.settings = Settings({"os": ["Windows"],
                           "compiler": {"msvc": {"version": ["193"], "cppstd": ["20"],
                                                 "update": [None]}},
                           "build_type": ["Release"],
                           "arch": ["x86"]})
    c.settings.build_type = "Release"
    c.settings.arch = "x86"
    c.settings.compiler = "msvc"
    c.settings.compiler.version = "193"
    c.settings.compiler.cppstd = "20"
    c.settings.os = "Windows"
    c.settings_build = c.settings
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    c._conan_node.transitive_deps = {}
    return c


def test_toolset(conanfile_msvc):
    toolchain = CMakeToolchain(conanfile_msvc)
    assert 'set(CMAKE_GENERATOR_TOOLSET "v143" CACHE STRING "" FORCE)' in toolchain.content
    assert 'Visual Studio 17 2022' in toolchain.generator
    assert 'CMAKE_CXX_STANDARD 20' in toolchain.content


def test_toolset_x64(conanfile_msvc):
    # https://github.com/conan-io/conan/issues/11144
    conanfile_msvc.conf.define("tools.cmake.cmaketoolchain:toolset_arch", "x64")
    toolchain = CMakeToolchain(conanfile_msvc)
    assert 'set(CMAKE_GENERATOR_TOOLSET "v143,host=x64" CACHE STRING "" FORCE)' in toolchain.content
    assert 'Visual Studio 17 2022' in toolchain.generator
    assert 'CMAKE_CXX_STANDARD 20' in toolchain.content


def test_older_msvc_toolset():
    c = ConanFile(None)
    c.settings = Settings({"os": ["Windows"],
                           "compiler": {"msvc": {"version": ["170"], "update": [None],
                                                 "cppstd": ["98"]}},
                           "build_type": ["Release"],
                           "arch": ["x86"]})
    c.settings.build_type = "Release"
    c.settings.arch = "x86"
    c.settings.compiler = "msvc"
    c.settings.compiler.version = "170"
    c.settings.compiler.cppstd = "98"
    c.settings.os = "Windows"
    c.settings_build = c.settings
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    c._conan_node.transitive_deps = {}
    toolchain = CMakeToolchain(c)
    content = toolchain.content
    assert 'CMAKE_GENERATOR_TOOLSET "v110"' in content
    # As by the CMake docs, this has no effect for VS < 2015
    assert 'CMAKE_CXX_STANDARD 98' in content


def test_msvc_xp_toolsets():
    c = ConanFile(None)
    c.settings = Settings({"os": ["Windows"],
                           "compiler": {"msvc": {"version": ["170"], "update": [None],
                                                 "cppstd": ["98"], "toolset": [None, "v110_xp"]}},
                           "build_type": ["Release"],
                           "arch": ["x86"]})
    c.settings.build_type = "Release"
    c.settings.arch = "x86"
    c.settings.compiler = "msvc"
    c.settings.compiler.version = "170"
    c.settings.compiler.toolset = "v110_xp"
    c.settings.compiler.cppstd = "98"
    c.settings.os = "Windows"
    c.settings_build = c.settings
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    c._conan_node.transitive_deps = {}
    toolchain = CMakeToolchain(c)
    content = toolchain.content
    assert 'CMAKE_GENERATOR_TOOLSET "v110_xp"' in content
    # As by the CMake docs, this has no effect for VS < 2015
    assert 'CMAKE_CXX_STANDARD 98' in content


@pytest.fixture
def conanfile_linux():
    c = ConanFile()
    c.settings = Settings({"os": ["Linux"],
                           "compiler": {"gcc": {"version": ["11"], "cppstd": ["20"]}},
                           "build_type": ["Release"],
                           "arch": ["x86_64"]})
    c.settings.build_type = "Release"
    c.settings.arch = "x86_64"
    c.settings.compiler = "gcc"
    c.settings.compiler.version = "11"
    c.settings.compiler.cppstd = "20"
    c.settings.os = "Linux"
    c.settings_build = c.settings
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    c._conan_node.transitive_deps = {}
    return c


def test_no_fpic_when_not_an_option(conanfile_linux):
    toolchain = CMakeToolchain(conanfile_linux)
    content = toolchain.content
    assert 'set(CMAKE_POSITION_INDEPENDENT_CODE' not in content


@pytest.fixture
def conanfile_linux_shared():
    c = ConanFile()
    c.options = Options({"fPIC": [True, False],
                         "shared": [True, False]},
                        {"fPIC": False, "shared": True, })
    c.settings = Settings({"os": ["Linux"],
                           "compiler": {"gcc": {"version": ["11"], "cppstd": ["20"]}},
                           "build_type": ["Release"],
                           "arch": ["x86_64"]})
    c.settings.build_type = "Release"
    c.settings.arch = "x86_64"
    c.settings.compiler = "gcc"
    c.settings.compiler.version = "11"
    c.settings.compiler.cppstd = "20"
    c.settings.os = "Linux"
    c.settings_build = c.settings
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    c._conan_node.transitive_deps = {}
    return c


@pytest.mark.parametrize("fPIC", [True, False])
def test_fpic_when_shared_true(conanfile_linux_shared, fPIC):
    conanfile_linux_shared.options.fPIC = fPIC
    toolchain = CMakeToolchain(conanfile_linux_shared)
    cmake_value = 'ON' if fPIC else 'OFF'
    content = toolchain.content
    assert 'set(CMAKE_POSITION_INDEPENDENT_CODE {} CACHE BOOL'.format(cmake_value) in content


def test_fpic_when_not_shared(conanfile_linux_shared):
    conanfile_linux_shared.options.shared = False
    toolchain = CMakeToolchain(conanfile_linux_shared)
    content = toolchain.content
    assert 'set(CMAKE_POSITION_INDEPENDENT_CODE' in content


@pytest.fixture
def conanfile_windows_fpic():
    c = ConanFile()
    c.settings = "os", "compiler", "build_type", "arch"
    c.options = Options({"fPIC": [True, False]},
                        {"fPIC": True})
    c.settings = Settings({"os": ["Windows"],
                           "compiler": {"gcc": {"libcxx": ["libstdc++"]}},
                           "build_type": ["Release"],
                           "arch": ["x86"]})
    c.settings.build_type = "Release"
    c.settings.arch = "x86"
    c.settings.compiler = "gcc"
    c.settings.compiler.libcxx = "libstdc++"
    c.settings.os = "Windows"
    c.settings_build = c.settings
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    c._conan_node.transitive_deps = {}
    return c


def test_no_fpic_on_windows(conanfile_windows_fpic):
    toolchain = CMakeToolchain(conanfile_windows_fpic)
    content = toolchain.content
    assert 'set(CMAKE_POSITION_INDEPENDENT_CODE' not in content


@pytest.fixture
def conanfile_linux_fpic():
    c = ConanFile()
    c.settings = "os", "compiler", "build_type", "arch"
    c.options = Options({"fPIC": [True, False]},
                        {"fPIC": False,})
    c.settings = Settings({"os": ["Linux"],
                           "compiler": {"gcc": {"version": ["11"], "cppstd": ["20"]}},
                           "build_type": ["Release"],
                           "arch": ["x86_64"]})
    c.settings.build_type = "Release"
    c.settings.arch = "x86_64"
    c.settings.compiler = "gcc"
    c.settings.compiler.version = "11"
    c.settings.compiler.cppstd = "20"
    c.settings.os = "Linux"
    c.settings_build = c.settings
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    c._conan_node.transitive_deps = {}
    return c


def test_fpic_disabled(conanfile_linux_fpic):
    conanfile_linux_fpic.options.fPIC = False
    toolchain = CMakeToolchain(conanfile_linux_fpic)
    content = toolchain.content
    assert 'set(CMAKE_POSITION_INDEPENDENT_CODE OFF' in content


def test_fpic_enabled(conanfile_linux_fpic):
    conanfile_linux_fpic.options.fPIC = True
    toolchain = CMakeToolchain(conanfile_linux_fpic)
    content = toolchain.content
    assert 'set(CMAKE_POSITION_INDEPENDENT_CODE ON' in content


def test_libcxx_abi_flag():
    c = ConanFile()
    c.settings = "os", "compiler", "build_type", "arch"
    c.settings = Settings.loads(get_default_settings_yml())
    c.settings.build_type = "Release"
    c.settings.arch = "x86_64"
    c.settings.compiler = "gcc"
    c.settings.compiler.version = "11"
    c.settings.compiler.cppstd = "20"
    c.settings.compiler.libcxx = "libstdc++"
    c.settings.os = "Linux"
    c.settings_build = c.settings
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    c._conan_node.transitive_deps = {}

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


@pytest.mark.parametrize("os,os_sdk,arch,expected_sdk", [
    ("Macos", None, "x86_64", "macosx"),
    ("Macos", None, "armv7", "macosx"),
    ("iOS", "iphonesimulator", "armv8", "iphonesimulator"),
    ("watchOS", "watchsimulator", "armv8", "watchsimulator")
])
def test_apple_cmake_osx_sysroot(os, os_sdk, arch, expected_sdk):
    """
    Testing if CMAKE_OSX_SYSROOT is correctly set.
    Issue related: https://github.com/conan-io/conan/issues/10275
    """
    c = ConanFile()
    c.settings = "os", "compiler", "build_type", "arch"
    c.settings = Settings.loads(get_default_settings_yml())
    c.settings.os = os
    if os_sdk:
        c.settings.os.sdk = os_sdk
    c.settings.build_type = "Release"
    c.settings.arch = arch
    c.settings.compiler = "apple-clang"
    c.settings.compiler.version = "13.0"
    c.settings.compiler.libcxx = "libc++"
    c.settings.compiler.cppstd = "17"
    c.settings_build = c.settings
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []
    c._conan_node.transitive_deps = {}

    toolchain = CMakeToolchain(c)
    content = toolchain.content
    assert 'set(CMAKE_OSX_SYSROOT %s CACHE STRING "" FORCE)' % expected_sdk in content


@pytest.mark.parametrize("os,arch,expected_sdk", [
    ("iOS", "x86_64", ""),
    ("watchOS", "armv8", ""),
    ("tvOS", "x86_64", "")
])
def test_apple_cmake_osx_sysroot_sdk_mandatory(os, arch, expected_sdk):
    """
    Testing if CMAKE_OSX_SYSROOT is correctly set.
    Issue related: https://github.com/conan-io/conan/issues/10275
    """
    c = ConanFile()
    c.settings = "os", "compiler", "build_type", "arch"
    c.settings = Settings.loads(get_default_settings_yml())
    c.settings.os = os
    c.settings.build_type = "Release"
    c.settings.arch = arch
    c.settings.compiler = "apple-clang"
    c.settings.compiler.version = "13.0"
    c.settings.compiler.libcxx = "libc++"
    c.settings.compiler.cppstd = "17"
    c.settings_build = c.settings
    c.conf = Conf()
    c.folders.set_base_generators(".")
    c._conan_node = Mock()
    c._conan_node.dependencies = []

    with pytest.raises(ConanException) as excinfo:
        CMakeToolchain(c).content()
        assert "Please, specify a suitable value for os.sdk." % expected_sdk in str(excinfo.value)


def test_variables_types(conanfile):
    generator_folder = temp_folder()
    conanfile.folders.set_base_generators(generator_folder)
    # This is a trick for 1.X to use base_generator and not install folder
    conanfile.folders.generators = "here"

    toolchain = CMakeToolchain(conanfile)
    toolchain.variables["FOO"] = True
    toolchain.generate()

    contents = load(os.path.join(conanfile.generators_folder, "conan_toolchain.cmake"))
    assert 'set(FOO ON CACHE BOOL "Variable FOO conan-toolchain defined")' in contents


def test_compilers_block(conanfile):
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


def test_linker_scripts_block(conanfile):
    conanfile.conf.define("tools.build:linker_scripts", ["path_to_first_linker_script", "path_to_second_linker_script"])
    toolchain = CMakeToolchain(conanfile)
    content = toolchain.content
    assert f'string(APPEND CONAN_EXE_LINKER_FLAGS -T"path_to_first_linker_script" -T"path_to_second_linker_script")' in content
