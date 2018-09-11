import re
import unittest
from collections import namedtuple

from conans.client.generators.cmake_multi import CMakeMultiGenerator
from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.client.generators.cmake import CMakeGenerator
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference
from conans.client.conf import default_settings_yml
from conans.test.utils.test_files import temp_folder
from conans.util.files import save
import os
from conans.model.env_info import EnvValues


class CMakeGeneratorTest(unittest.TestCase):

    def _extract_macro(self, name, text):
        pattern = ".*(macro\(%s\).*?endmacro\(\)).*" % name
        return re.sub(pattern, r"\1", text, flags=re.DOTALL)

    def variables_setup_test(self):
        conanfile = ConanFile(None, None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.defines = ["MYDEFINE1"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder2")
        cpp_info.defines = ["MYDEFINE2"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        conanfile.deps_user_info["LIB1"].myvar = "myvalue"
        conanfile.deps_user_info["LIB1"].myvar2 = "myvalue2"
        conanfile.deps_user_info["lib2"].MYVAR2 = "myvalue4"
        generator = CMakeGenerator(conanfile)
        content = generator.content
        cmake_lines = content.splitlines()
        self.assertIn('set(CONAN_DEFINES_MYPKG "-DMYDEFINE1")', cmake_lines)
        self.assertIn('set(CONAN_DEFINES_MYPKG2 "-DMYDEFINE2")', cmake_lines)
        self.assertIn('set(CONAN_COMPILE_DEFINITIONS_MYPKG "MYDEFINE1")', cmake_lines)
        self.assertIn('set(CONAN_COMPILE_DEFINITIONS_MYPKG2 "MYDEFINE2")', cmake_lines)

        self.assertIn('set(CONAN_USER_LIB1_myvar "myvalue")', cmake_lines)
        self.assertIn('set(CONAN_USER_LIB1_myvar2 "myvalue2")', cmake_lines)
        self.assertIn('set(CONAN_USER_LIB2_MYVAR2 "myvalue4")', cmake_lines)

    def paths_cmake_multi_user_vars_test(self):
        settings_mock = namedtuple("Settings", "build_type, os, os_build, constraint")
        conanfile = ConanFile(None, None)
        conanfile.initialize(settings_mock("Release", None, None,
                                           lambda x, raise_undefined_field: x), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        tmp_folder = temp_folder()
        save(os.path.join(tmp_folder, "lib", "mylib.lib"), "")
        save(os.path.join(tmp_folder, "include", "myheader.h"), "")
        cpp_info = CppInfo(tmp_folder)
        cpp_info.release.libs = ["hello"]
        cpp_info.debug.libs = ["hello_D"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = CMakeMultiGenerator(conanfile)
        release = generator.content["conanbuildinfo_release.cmake"]
        release = release.replace(tmp_folder.replace("\\", "/"), "root_folder")
        cmake_lines = release.splitlines()
        self.assertIn('set(CONAN_INCLUDE_DIRS_MYPKG_RELEASE "root_folder/include")', cmake_lines)
        self.assertIn('set(CONAN_LIB_DIRS_MYPKG_RELEASE "root_folder/lib")', cmake_lines)

    def paths_cmake_test(self):
        settings_mock = namedtuple("Settings", "build_type, os, os_build, constraint, items")
        conanfile = ConanFile(None, None)
        conanfile.initialize(settings_mock(None, None, None,
                                                        lambda x, raise_undefined_field: x,
                                                        lambda: {}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        tmp_folder = temp_folder()
        save(os.path.join(tmp_folder, "lib", "mylib.lib"), "")
        save(os.path.join(tmp_folder, "include", "myheader.h"), "")
        cpp_info = CppInfo(tmp_folder)
        cpp_info.release.libs = ["hello"]
        cpp_info.debug.libs = ["hello_D"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = CMakeGenerator(conanfile)
        content = generator.content
        content = content.replace(tmp_folder.replace("\\", "/"), "root_folder")
        cmake_lines = content.splitlines()
        self.assertIn('set(CONAN_INCLUDE_DIRS_MYPKG_RELEASE "root_folder/include")', cmake_lines)
        self.assertIn('set(CONAN_LIB_DIRS_MYPKG_RELEASE "root_folder/lib")', cmake_lines)

    def variables_cmake_multi_user_vars_test(self):
        settings_mock = namedtuple("Settings", "build_type, os, os_build, constraint")
        conanfile = ConanFile(None, None)
        conanfile.initialize(settings_mock("Release", None, None, lambda x, raise_undefined_field: x,),
                             EnvValues())
        conanfile.deps_user_info["LIB1"].myvar = "myvalue"
        conanfile.deps_user_info["LIB1"].myvar2 = "myvalue2"
        conanfile.deps_user_info["lib2"].MYVAR2 = "myvalue4"
        generator = CMakeMultiGenerator(conanfile)
        content = generator.content["conanbuildinfo_multi.cmake"]
        cmake_lines = content.splitlines()
        self.assertIn('set(CONAN_USER_LIB1_myvar "myvalue")', cmake_lines)
        self.assertIn('set(CONAN_USER_LIB1_myvar2 "myvalue2")', cmake_lines)
        self.assertIn('set(CONAN_USER_LIB2_MYVAR2 "myvalue4")', cmake_lines)

    def variables_cmake_multi_user_vars_escape_test(self):
        settings_mock = namedtuple("Settings", "build_type, os, os_build, constraint")
        conanfile = ConanFile(None, None)
        conanfile.initialize(settings_mock("Release", None, None, lambda x, raise_undefined_field: x,),
                             EnvValues())
        conanfile.deps_user_info["FOO"].myvar = 'my"value"'
        conanfile.deps_user_info["FOO"].myvar2 = 'my${value}'
        conanfile.deps_user_info["FOO"].myvar3 = 'my\\value'
        generator = CMakeMultiGenerator(conanfile)
        content = generator.content["conanbuildinfo_multi.cmake"]
        cmake_lines = content.splitlines()
        self.assertIn(r'set(CONAN_USER_FOO_myvar "my\"value\"")', cmake_lines)
        self.assertIn(r'set(CONAN_USER_FOO_myvar2 "my\${value}")', cmake_lines)
        self.assertIn(r'set(CONAN_USER_FOO_myvar3 "my\\value")', cmake_lines)

    def multi_flag_test(self):
        conanfile = ConanFile(None, None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.includedirs.append("other_include_dir")
        cpp_info.cppflags = ["-DGTEST_USE_OWN_TR1_TUPLE=1", "-DGTEST_LINKED_AS_SHARED_LIBRARY=1"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder2")
        cpp_info.cflags = ["-DSOMEFLAG=1"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = CMakeGenerator(conanfile)
        content = generator.content
        cmake_lines = content.splitlines()
        self.assertIn('set(CONAN_C_FLAGS_MYPKG2 "-DSOMEFLAG=1")', cmake_lines)
        self.assertIn('set(CONAN_CXX_FLAGS_MYPKG "-DGTEST_USE_OWN_TR1_TUPLE=1'
                      ' -DGTEST_LINKED_AS_SHARED_LIBRARY=1")', cmake_lines)
        self.assertIn('set(CONAN_C_FLAGS "-DSOMEFLAG=1 ${CONAN_C_FLAGS}")', cmake_lines)
        self.assertIn('set(CONAN_CXX_FLAGS "-DGTEST_USE_OWN_TR1_TUPLE=1'
                      ' -DGTEST_LINKED_AS_SHARED_LIBRARY=1 ${CONAN_CXX_FLAGS}")', cmake_lines)

    def escaped_flags_test(self):
        conanfile = ConanFile(None, None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.includedirs.append("other_include_dir")
        cpp_info.cppflags = ["-load", r"C:\foo\bar.dll"]
        cpp_info.cflags = ["-load", r"C:\foo\bar2.dll"]
        cpp_info.defines = ['MY_DEF=My string', 'MY_DEF2=My other string']
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = CMakeGenerator(conanfile)
        content = generator.content
        cmake_lines = content.splitlines()
        self.assertIn(r'set(CONAN_C_FLAGS_MYPKG "-load C:\\foo\\bar2.dll")', cmake_lines)
        self.assertIn(r'set(CONAN_CXX_FLAGS_MYPKG "-load C:\\foo\\bar.dll")', cmake_lines)
        self.assertIn(r'set(CONAN_DEFINES_MYPKG "-DMY_DEF=My string"', cmake_lines)
        self.assertIn('\t\t\t"-DMY_DEF2=My other string")', cmake_lines)

    def aux_cmake_test_setup_test(self):
        conanfile = ConanFile(None, None)
        conanfile.initialize(Settings({}), EnvValues())
        generator = CMakeGenerator(conanfile)
        aux_cmake_test_setup = generator.content

        # extract the conan_basic_setup macro
        macro = self._extract_macro("conan_basic_setup", aux_cmake_test_setup)
        self.assertEqual("""macro(conan_basic_setup)
    set(options TARGETS NO_OUTPUT_DIRS SKIP_RPATH KEEP_RPATHS SKIP_STD SKIP_FPIC)
    cmake_parse_arguments(ARGUMENTS "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN} )
    if(CONAN_EXPORTED)
        message(STATUS "Conan: called by CMake conan helper")
    endif()
    if(CONAN_IN_LOCAL_CACHE)
        message(STATUS "Conan: called inside local cache")
    endif()
    conan_check_compiler()
    if(NOT ARGUMENTS_NO_OUTPUT_DIRS)
        conan_output_dirs_setup()
    endif()
    conan_set_find_library_paths()
    if(NOT ARGUMENTS_TARGETS)
        message(STATUS "Conan: Using cmake global configuration")
        conan_global_flags()
    else()
        message(STATUS "Conan: Using cmake targets configuration")
        conan_define_targets()
    endif()
    if(ARGUMENTS_SKIP_RPATH)
        # Change by "DEPRECATION" or "SEND_ERROR" when we are ready
        message(WARNING "Conan: SKIP_RPATH is deprecated, it has been renamed to KEEP_RPATHS")
    endif()
    if(NOT ARGUMENTS_SKIP_RPATH AND NOT ARGUMENTS_KEEP_RPATHS)
        # Parameter has renamed, but we keep the compatibility with old SKIP_RPATH
        message(STATUS "Conan: Adjusting default RPATHs Conan policies")
        conan_set_rpath()
    endif()
    if(NOT ARGUMENTS_SKIP_STD)
        message(STATUS "Conan: Adjusting language standard")
        conan_set_std()
    endif()
    if(NOT ARGUMENTS_SKIP_FPIC)
        conan_set_fpic()
    endif()
    conan_set_vs_runtime()
    conan_set_libcxx()
    conan_set_find_paths()
endmacro()""", macro)

        # extract the conan_set_find_paths macro
        macro = self._extract_macro("conan_set_find_paths", aux_cmake_test_setup)
        self.assertEqual("""macro(conan_set_find_paths)
    # CMAKE_MODULE_PATH does not have Debug/Release config, but there are variables
    # CONAN_CMAKE_MODULE_PATH_DEBUG to be used by the consumer
    # CMake can find findXXX.cmake files in the root of packages
    set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_MODULE_PATH})

    # Make find_package() to work
    set(CMAKE_PREFIX_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_PREFIX_PATH})

    # Set the find root path (cross build)
    set(CMAKE_FIND_ROOT_PATH ${CONAN_CMAKE_FIND_ROOT_PATH} ${CMAKE_FIND_ROOT_PATH})
    if(CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM)
        set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM ${CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM})
    endif()
    if(CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY)
        set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ${CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY})
    endif()
    if(CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE)
        set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ${CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE})
    endif()
endmacro()""", macro)

    def name_and_version_are_generated_test(self):
        conanfile = ConanFile(None, None)
        conanfile.initialize(Settings({}), EnvValues())
        conanfile.name = "MyPkg"
        conanfile.version = "1.1.0"
        generator = CMakeGenerator(conanfile)
        content = generator.content
        cmake_lines = content.splitlines()
        self.assertIn('set(CONAN_PACKAGE_NAME MyPkg)', cmake_lines)
        self.assertIn('set(CONAN_PACKAGE_VERSION 1.1.0)', cmake_lines)

    def settings_are_generated_tests(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.compiler.runtime = "MD"
        settings.arch = "x86"
        settings.build_type = "Debug"
        conanfile = ConanFile(None, None)
        conanfile.initialize(Settings({}), EnvValues())
        conanfile.settings = settings
        generator = CMakeGenerator(conanfile)
        content = generator.content
        cmake_lines = content.splitlines()
        self.assertIn('set(CONAN_SETTINGS_BUILD_TYPE "Debug")', cmake_lines)
        self.assertIn('set(CONAN_SETTINGS_ARCH "x86")', cmake_lines)
        self.assertIn('set(CONAN_SETTINGS_COMPILER "Visual Studio")', cmake_lines)
        self.assertIn('set(CONAN_SETTINGS_COMPILER_VERSION "12")', cmake_lines)
        self.assertIn('set(CONAN_SETTINGS_COMPILER_RUNTIME "MD")', cmake_lines)
        self.assertIn('set(CONAN_SETTINGS_OS "Windows")', cmake_lines)
