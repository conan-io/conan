import unittest

from conans import CMake
from conans.client.build.cmake_flags import get_generator
from conans.test.utils.conanfile import MockSettings, ConanFileMock


class CMakeGeneratorTest(unittest.TestCase):

    def test_cmake_default_generator_linux(self):
        settings = MockSettings({"os_build": "Linux"})
        generator = get_generator(settings)
        self.assertEquals("Unix Makefiles", generator)
        self._test_default_generator_cmake(settings, "Unix Makefiles")

    def test_cmake_default_generator_osx(self):
        settings = MockSettings({"os_build": "Macos"})
        generator = get_generator(settings)
        self.assertEquals("Unix Makefiles", generator)
        self._test_default_generator_cmake(settings, "Unix Makefiles")

    def test_default_generator_windows(self):
        settings = MockSettings({"os_build": "Windows"})
        generator = get_generator(settings)
        self.assertEquals("MinGW Makefiles", generator)
        self._test_default_generator_cmake(settings, "MinGW Makefiles")

    def _test_default_generator_cmake(self, settings, generator):
        conanfile = ConanFileMock()
        conanfile.settings = settings
        cmake = CMake(conanfile)
        self.assertEquals(generator, cmake.generator)
        self.assertIn('-G "{}"'.format(generator), cmake.command_line)

