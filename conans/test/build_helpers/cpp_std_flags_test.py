import unittest

from conans.client.build.cppstd_flags import cppstd_flag, cppstd_default


class CompilerFlagsTest(unittest.TestCase):

    def test_gcc_cppstd_flags(self):
        self.assertEquals(cppstd_flag("gcc", "4.2", "98"), "-std=c++98")
        self.assertEquals(cppstd_flag("gcc", "4.2", "gnu98"), "-std=gnu++98")
        self.assertEquals(cppstd_flag("gcc", "4.2", "11"), None)
        self.assertEquals(cppstd_flag("gcc", "4.2", "14"), None)

        self.assertEquals(cppstd_flag("gcc", "4.3", "98"), "-std=c++98")
        self.assertEquals(cppstd_flag("gcc", "4.3", "gnu98"), "-std=gnu++98")
        self.assertEquals(cppstd_flag("gcc", "4.3", "11"), "-std=c++0x")
        self.assertEquals(cppstd_flag("gcc", "4.3", "14"), None)

        self.assertEquals(cppstd_flag("gcc", "4.6", "11"), '-std=c++0x')
        self.assertEquals(cppstd_flag("gcc", "4.6", "14"), None)

        self.assertEquals(cppstd_flag("gcc", "4.7", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("gcc", "4.7", "14"), None)

        self.assertEquals(cppstd_flag("gcc", "4.8", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("gcc", "4.8", "14"), '-std=c++1y')
        self.assertEquals(cppstd_flag("gcc", "4.8", "17"), None)

        self.assertEquals(cppstd_flag("gcc", "4.9", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("gcc", "4.9", "14"), '-std=c++14')
        self.assertEquals(cppstd_flag("gcc", "4.9", "17"), None)

        self.assertEquals(cppstd_flag("gcc", "5", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("gcc", "5", "14"), '-std=c++14')
        self.assertEquals(cppstd_flag("gcc", "5", "gnu14"), '-std=gnu++14')
        self.assertEquals(cppstd_flag("gcc", "5", "17"), None)

        self.assertEquals(cppstd_flag("gcc", "5.1", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("gcc", "5.1", "14"), '-std=c++14')
        self.assertEquals(cppstd_flag("gcc", "5.1", "17"), '-std=c++1z')

        self.assertEquals(cppstd_flag("gcc", "7", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("gcc", "7", "14"), '-std=c++14')
        self.assertEquals(cppstd_flag("gcc", "7", "17"), '-std=c++1z')

    def test_gcc_cppstd_defaults(self):
        self.assertEquals(cppstd_default("gcc", "4"), "gnu98")
        self.assertEquals(cppstd_default("gcc", "5"), "gnu98")
        self.assertEquals(cppstd_default("gcc", "6"), "gnu98")
        self.assertEquals(cppstd_default("gcc", "6.1"), "gnu14")
        self.assertEquals(cppstd_default("gcc", "7.3"), "gnu14")

    def test_clang_cppstd_flags(self):
        self.assertEquals(cppstd_flag("clang", "2.0", "98"), None)
        self.assertEquals(cppstd_flag("clang", "2.0", "gnu98"), None)
        self.assertEquals(cppstd_flag("clang", "2.0", "11"), None)
        self.assertEquals(cppstd_flag("clang", "2.0", "14"), None)

        self.assertEquals(cppstd_flag("clang", "2.1", "98"), "-std=c++98")
        self.assertEquals(cppstd_flag("clang", "2.1", "gnu98"), "-std=gnu++98")
        self.assertEquals(cppstd_flag("clang", "2.1", "11"), "-std=c++0x")
        self.assertEquals(cppstd_flag("clang", "2.1", "14"), None)

        self.assertEquals(cppstd_flag("clang", "3.0", "11"), '-std=c++0x')
        self.assertEquals(cppstd_flag("clang", "3.0", "14"), None)

        self.assertEquals(cppstd_flag("clang", "3.1", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("clang", "3.1", "14"), None)

        self.assertEquals(cppstd_flag("clang", "3.4", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("clang", "3.4", "14"), '-std=c++1y')
        self.assertEquals(cppstd_flag("clang", "3.4", "17"), None)

        self.assertEquals(cppstd_flag("clang", "3.5", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("clang", "3.5", "14"), '-std=c++14')
        self.assertEquals(cppstd_flag("clang", "3.5", "17"), '-std=c++1z')

        self.assertEquals(cppstd_flag("clang", "5", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("clang", "5", "14"), '-std=c++14')
        self.assertEquals(cppstd_flag("clang", "5", "gnu14"), '-std=gnu++14')
        self.assertEquals(cppstd_flag("clang", "5", "17"), '-std=c++1z')

        self.assertEquals(cppstd_flag("clang", "5.1", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("clang", "5.1", "14"), '-std=c++14')
        self.assertEquals(cppstd_flag("clang", "5.1", "17"), '-std=c++1z')

        self.assertEquals(cppstd_flag("clang", "7", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("clang", "7", "14"), '-std=c++14')
        self.assertEquals(cppstd_flag("clang", "7", "17"), '-std=c++1z')

    def test_clang_cppstd_defaults(self):
        self.assertEquals(cppstd_default("clang", "2"), "gnu++98")
        self.assertEquals(cppstd_default("clang", "2.1"), "gnu++98")
        self.assertEquals(cppstd_default("clang", "3.0"), "gnu++98")
        self.assertEquals(cppstd_default("clang", "3.1"), "gnu++98")
        self.assertEquals(cppstd_default("clang", "3.4"), "gnu++98")
        self.assertEquals(cppstd_default("clang", "3.5"), "gnu++98")
        self.assertEquals(cppstd_default("clang", "5"), "gnu++98")
        self.assertEquals(cppstd_default("clang", "5.1"), "gnu++98")
        self.assertEquals(cppstd_default("clang", "7"), "gnu++98")

    def test_apple_clang_cppstd_flags(self):
        self.assertEquals(cppstd_flag("apple-clang", "3.9", "98"), None)
        self.assertEquals(cppstd_flag("apple-clang", "3.9", "gnu98"), None)
        self.assertEquals(cppstd_flag("apple-clang", "3.9", "11"), None)
        self.assertEquals(cppstd_flag("apple-clang", "3.9", "14"), None)

        self.assertEquals(cppstd_flag("apple-clang", "4.0", "98"), "-std=c++98")
        self.assertEquals(cppstd_flag("apple-clang", "4.0", "gnu98"), "-std=gnu++98")
        self.assertEquals(cppstd_flag("apple-clang", "4.0", "11"), "-std=c++11")
        self.assertEquals(cppstd_flag("apple-clang", "4.0", "14"), None)

        self.assertEquals(cppstd_flag("apple-clang", "5.0", "98"), "-std=c++98")
        self.assertEquals(cppstd_flag("apple-clang", "5.0", "gnu98"), "-std=gnu++98")
        self.assertEquals(cppstd_flag("apple-clang", "5.0", "11"), "-std=c++11")
        self.assertEquals(cppstd_flag("apple-clang", "5.0", "14"), None)

        self.assertEquals(cppstd_flag("apple-clang", "5.1", "98"), "-std=c++98")
        self.assertEquals(cppstd_flag("apple-clang", "5.1", "gnu98"), "-std=gnu++98")
        self.assertEquals(cppstd_flag("apple-clang", "5.1", "11"), "-std=c++11")
        self.assertEquals(cppstd_flag("apple-clang", "5.1", "14"), "-std=c++1y")

        self.assertEquals(cppstd_flag("apple-clang", "6.1", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("apple-clang", "6.1", "14"), '-std=c++14')
        self.assertEquals(cppstd_flag("apple-clang", "6.1", "17"), "-std=c++1z")

        self.assertEquals(cppstd_flag("apple-clang", "7", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("apple-clang", "7", "14"), '-std=c++14')
        self.assertEquals(cppstd_flag("apple-clang", "7", "17"), "-std=c++1z")

        self.assertEquals(cppstd_flag("apple-clang", "8", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("apple-clang", "8", "14"), '-std=c++14')
        self.assertEquals(cppstd_flag("apple-clang", "8", "17"), "-std=c++1z")

        self.assertEquals(cppstd_flag("apple-clang", "9", "11"), '-std=c++11')
        self.assertEquals(cppstd_flag("apple-clang", "9", "14"), '-std=c++14')
        self.assertEquals(cppstd_flag("apple-clang", "9", "17"), "-std=c++1z")

    def test_apple_clang_cppstd_defaults(self):
        self.assertEquals(cppstd_default("apple-clang", "2"), "gnu++98")
        self.assertEquals(cppstd_default("apple-clang", "3"), "gnu++98")
        self.assertEquals(cppstd_default("apple-clang", "4"), "gnu++98")
        self.assertEquals(cppstd_default("apple-clang", "5"), "gnu++98")
        self.assertEquals(cppstd_default("apple-clang", "6"), "gnu++98")
        self.assertEquals(cppstd_default("apple-clang", "7"), "gnu++98")
        self.assertEquals(cppstd_default("apple-clang", "8"), "gnu++98")
        self.assertEquals(cppstd_default("apple-clang", "9"), "gnu++98")

    def test_visual_cppstd_flags(self):
        self.assertEquals(cppstd_flag("Visual Studio", "12", "11"), None)
        self.assertEquals(cppstd_flag("Visual Studio", "12", "14"), None)
        self.assertEquals(cppstd_flag("Visual Studio", "12", "17"), None)

        self.assertEquals(cppstd_flag("Visual Studio", "14", "11"), None)
        self.assertEquals(cppstd_flag("Visual Studio", "14", "14"), '/std:c++14')
        self.assertEquals(cppstd_flag("Visual Studio", "14", "17"), '/std:c++latest')

        self.assertEquals(cppstd_flag("Visual Studio", "17", "11"), None)
        self.assertEquals(cppstd_flag("Visual Studio", "17", "14"), '/std:c++14')
        self.assertEquals(cppstd_flag("Visual Studio", "17", "17"), '/std:c++17')

    def test_visual_cppstd_defaults(self):
        self.assertEquals(cppstd_default("Visual Studio", "11"), None)
        self.assertEquals(cppstd_default("Visual Studio", "12"), None)
        self.assertEquals(cppstd_default("Visual Studio", "13"), None)
        self.assertEquals(cppstd_default("Visual Studio", "14"), "14")
        self.assertEquals(cppstd_default("Visual Studio", "15"), "14")
