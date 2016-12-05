import re
import unittest
from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.client.generators.cmake import CMakeGenerator


class CMakeGeneratorTest(unittest.TestCase):

    def _extract_macro(self, name, text):
        pattern = ".*(macro\(%s\).*?endmacro\(\)).*" % name
        return re.sub(pattern, r"\1", text, flags=re.DOTALL)

    def aux_cmake_test_setup_test(self):
        conanfile = ConanFile(None, None, Settings({}), None)
        generator = CMakeGenerator(conanfile)
        aux_cmake_test_setup = generator._aux_cmake_test_setup()

        # extract the conan_basic_setup macro
        macro = self._extract_macro("conan_basic_setup", aux_cmake_test_setup)
        self.assertEqual("""macro(conan_basic_setup)
    conan_check_compiler()
    conan_output_dirs_setup()
    conan_set_find_library_paths()
    if(NOT "${ARGV0}" STREQUAL "TARGETS")
        message(STATUS "Conan: Using cmake global configuration")
        conan_global_flags()
    else()
        message(STATUS "Conan: Using cmake targets configuration")
    endif()
    conan_set_rpath()
    conan_set_vs_runtime()
    conan_set_libcxx()
    conan_set_find_paths()
endmacro()""", macro)

        # extract the conan_set_find_paths macro
        macro = self._extract_macro("conan_set_find_paths", aux_cmake_test_setup)
        self.assertEqual("""macro(conan_set_find_paths)
    # CMake can find findXXX.cmake files in the root of packages
    set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_MODULE_PATH})

    # Make find_package() to work
    set(CMAKE_PREFIX_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_PREFIX_PATH})
endmacro()""", macro)
