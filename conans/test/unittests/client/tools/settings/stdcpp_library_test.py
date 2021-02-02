import unittest

from conans.client.tools.settings import stdcpp_library
from conans.client.conf import get_default_settings_yml
from conans.model.settings import Settings
from conans.test.utils.mocks import MockConanfile


class TestStdCppLibrary(unittest.TestCase):
    def test_stdcpp_library(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.compiler = "gcc"
        settings.compiler.libcxx = "libstdc++"
        conanfile = MockConanfile(settings)
        self.assertEqual("stdc++", stdcpp_library(conanfile))

        settings.compiler.libcxx = "libstdc++11"
        self.assertEqual("stdc++", stdcpp_library(conanfile))

        settings.compiler = "clang"
        settings.compiler.libcxx = "libc++"
        self.assertEqual("c++", stdcpp_library(conanfile))

        settings.compiler.libcxx = "c++_shared"
        self.assertEqual("c++_shared", stdcpp_library(conanfile))

        settings.compiler.libcxx = "c++_static"
        self.assertEqual("c++_static", stdcpp_library(conanfile))
