import platform
import unittest
from parameterized import parameterized

import pytest

from conans.client.build.cmake import CMake
from conans.client.conf import get_default_settings_yml
from conans.model.settings import Settings
from conans.test.utils.mocks import MockSettings, ConanFileMock


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
class CMakeAppleTest(unittest.TestCase):
    @parameterized.expand([('x86', 'Macos', 'i386', 'MacOSX.platform'),
                           ('x86_64', 'Macos', 'x86_64', 'MacOSX.platform'),
                           ('armv7', 'Macos', 'armv7', 'MacOSX.platform'),
                           ('armv8', 'Macos', 'arm64', 'MacOSX.platform'),
                           ('x86', 'iOS', 'i386', 'iPhoneSimulator.platform'),
                           ('x86_64', 'iOS', 'x86_64', 'iPhoneSimulator.platform'),
                           ('armv7', 'iOS', 'armv7', 'iPhoneOS.platform'),
                           ('armv8', 'iOS', 'arm64', 'iPhoneOS.platform'),
                           ('x86', 'watchOS', 'i386', 'WatchSimulator.platform'),
                           ('x86_64', 'watchOS', 'x86_64', 'WatchSimulator.platform'),
                           ('armv7', 'watchOS', 'armv7', 'WatchOS.platform'),
                           ('armv8', 'watchOS', 'arm64', 'WatchOS.platform'),
                           ('x86', 'tvOS', 'i386', 'AppleTVSimulator.platform'),
                           ('x86_64', 'tvOS', 'x86_64', 'AppleTVSimulator.platform'),
                           ('armv7', 'tvOS', 'armv7', 'AppleTVOS.platform'),
                           ('armv8', 'tvOS', 'arm64', 'AppleTVOS.platform')
                           ])
    def test_cmake_definitions(self, conan_arch, conan_os, expected_arch, expected_os):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = conan_os
        settings.compiler = "apple-clang"
        settings.compiler.version = "11.0"
        settings.arch = conan_arch

        conanfile = ConanFileMock()
        conanfile.settings = settings
        cmake = CMake(conanfile)

        self.assertEqual(cmake.definitions["CMAKE_OSX_ARCHITECTURES"], expected_arch)
        self.assertIn(expected_os, cmake.definitions["CMAKE_OSX_SYSROOT"])

    @parameterized.expand([('iOS', 'iPhoneOS.platform'),
                           ('Macos', 'MacOSX.platform'),
                           ('watchOS', 'WatchOS.platform'),
                           ('tvOS', 'AppleTVOS.platform')
                           ])
    def test_build_folder_vars(self, conan_os, expected_os):
        settings = MockSettings({"os": conan_os,
                                 "compiler": "apple-clang",
                                 "compiler.version": "11.0",
                                 "arch": "ios_fat"})
        conanfile = ConanFileMock()
        conanfile.settings = settings
        cmake = CMake(conanfile)

        self.assertNotIn("CMAKE_OSX_ARCHITECTURES", cmake.definitions)
        self.assertIn(expected_os, cmake.definitions["CMAKE_OSX_SYSROOT"])
