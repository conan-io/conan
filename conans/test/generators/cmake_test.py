import re, unittest
from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.client.generators.cmake import CMakeGenerator


class CMakeGeneratorTest(unittest.TestCase):

    def extractMacro(self, name, text):
        pattern = ".*(macro\(%s\).*?endmacro\(\)).*" % name
        return re.sub(pattern, r"\1", text, flags=re.DOTALL)

    def aux_cmake_test_setup_test(self):
        conanfile = ConanFile(None, None, Settings({}), None)
        generator = CMakeGenerator(conanfile)
        aux_cmake_test_setup = generator._aux_cmake_test_setup()

        # extract the conan_basic_setup macro
        macro = self.extractMacro("conan_basic_setup", aux_cmake_test_setup)
        self.assertEqual("""macro(conan_basic_setup)
    conan_check_compiler()
    conan_output_dirs_setup()
    conan_flags_setup()
    conan_set_find_paths()
endmacro()""", macro)
        
        # extract the conan_set_find_paths macro
        macro = self.extractMacro("conan_set_find_paths", aux_cmake_test_setup)
        self.assertEqual("""macro(conan_set_find_paths)
    # CMake can find findXXX.cmake files in the root of packages
    set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_MODULE_PATH})

    # Make find_package() to work
    set(CMAKE_PREFIX_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_PREFIX_PATH})
endmacro()""", macro)
