import unittest

from conans.client.build.cmake_flags import get_generator
from conans.test.utils.conanfile import MockSettings


class CMakeGeneratorTest(unittest.TestCase):

    def test_cmake_default_generator_linux(self):
        settings = MockSettings({"os_build": "Linux"})
        generator = get_generator(settings)
        self.assertEquals("Unix Makefiles", generator)

    def test_cmake_default_generator_osx(self):
        settings = MockSettings({"os_build": "Macos"})
        generator = get_generator(settings)
        self.assertEquals("Unix Makefiles", generator)

    def test_default_generator_windows(self):
        settings = MockSettings({"os_build": "Windows"})
        generator = get_generator(settings)
        self.assertEquals("MinGW Makefiles", generator)
