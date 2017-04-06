import re
import unittest
from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.client.generators.cmake import CMakeGenerator
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference


class CMakeGeneratorTest(unittest.TestCase):

    def _extract_macro(self, name, text):
        pattern = ".*(macro\(%s\).*?endmacro\(\)).*" % name
        return re.sub(pattern, r"\1", text, flags=re.DOTALL)

    def variables_setup_test(self):
        conanfile = ConanFile(None, None, Settings({}), None)
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder1")
        cpp_info.defines = ["MYDEFINE1"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo("dummy_root_folder2")
        cpp_info.defines = ["MYDEFINE2"]
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = CMakeGenerator(conanfile)
        content = generator.content
        cmake_lines = content.splitlines()
        self.assertIn("set(CONAN_DEFINES_MYPKG -DMYDEFINE1)", cmake_lines)
        self.assertIn("set(CONAN_DEFINES_MYPKG2 -DMYDEFINE2)", cmake_lines)
        self.assertIn("set(CONAN_COMPILE_DEFINITIONS_MYPKG MYDEFINE1)", cmake_lines)
        self.assertIn("set(CONAN_COMPILE_DEFINITIONS_MYPKG2 MYDEFINE2)", cmake_lines)

    def multi_flag_test(self):
        conanfile = ConanFile(None, None, Settings({}), None)
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

    def aux_cmake_test_setup_test(self):
        conanfile = ConanFile(None, None, Settings({}), None)
        generator = CMakeGenerator(conanfile)
        aux_cmake_test_setup = generator.content

        # extract the conan_basic_setup macro
        macro = self._extract_macro("conan_basic_setup", aux_cmake_test_setup)
        self.assertEqual("""macro(conan_basic_setup)
    if(CONAN_EXPORTED)
        message(STATUS "Conan: called by CMake conan helper")
    endif()
    conan_check_compiler()
    conan_output_dirs_setup()
    conan_set_find_library_paths()
    if(NOT "${ARGV0}" STREQUAL "TARGETS")
        message(STATUS "Conan: Using cmake global configuration")
        conan_global_flags()
    else()
        message(STATUS "Conan: Using cmake targets configuration")
        conan_define_targets()
    endif()
    conan_set_rpath()
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
