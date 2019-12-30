import unittest

from conans.client.build.cppstd_flags import cppstd_default, cppstd_flag


class CompilerFlagsTest(unittest.TestCase):

    def test_gcc_cppstd_flags(self):
        self.assertEqual(cppstd_flag("gcc", "4.2", "98"), "-std=c++98")
        self.assertEqual(cppstd_flag("gcc", "4.2", "gnu98"), "-std=gnu++98")
        self.assertEqual(cppstd_flag("gcc", "4.2", "11"), None)
        self.assertEqual(cppstd_flag("gcc", "4.2", "14"), None)

        self.assertEqual(cppstd_flag("gcc", "4.3", "98"), "-std=c++98")
        self.assertEqual(cppstd_flag("gcc", "4.3", "gnu98"), "-std=gnu++98")
        self.assertEqual(cppstd_flag("gcc", "4.3", "11"), "-std=c++0x")
        self.assertEqual(cppstd_flag("gcc", "4.3", "14"), None)

        self.assertEqual(cppstd_flag("gcc", "4.6", "11"), '-std=c++0x')
        self.assertEqual(cppstd_flag("gcc", "4.6", "14"), None)

        self.assertEqual(cppstd_flag("gcc", "4.7", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("gcc", "4.7", "14"), None)

        self.assertEqual(cppstd_flag("gcc", "4.8", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("gcc", "4.8", "14"), '-std=c++1y')
        self.assertEqual(cppstd_flag("gcc", "4.8", "17"), None)

        self.assertEqual(cppstd_flag("gcc", "4.9", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("gcc", "4.9", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("gcc", "4.9", "17"), None)

        self.assertEqual(cppstd_flag("gcc", "5", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("gcc", "5", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("gcc", "5", "gnu14"), '-std=gnu++14')
        self.assertEqual(cppstd_flag("gcc", "5", "17"), None)

        self.assertEqual(cppstd_flag("gcc", "5.1", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("gcc", "5.1", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("gcc", "5.1", "17"), '-std=c++1z')

        self.assertEqual(cppstd_flag("gcc", "7", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("gcc", "7", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("gcc", "7", "17"), '-std=c++17')

        self.assertEqual(cppstd_flag("gcc", "8", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("gcc", "8", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("gcc", "8", "17"), '-std=c++17')
        self.assertEqual(cppstd_flag("gcc", "8", "20"), '-std=c++2a')

    def test_gcc_cppstd_defaults(self):
        self.assertEqual(cppstd_default("gcc", "4", None, None), "gnu98")
        self.assertEqual(cppstd_default("gcc", "5", None, None), "gnu98")
        self.assertEqual(cppstd_default("gcc", "6", None, None), "gnu14")
        self.assertEqual(cppstd_default("gcc", "6.1", None, None), "gnu14")
        self.assertEqual(cppstd_default("gcc", "7.3", None, None), "gnu14")
        self.assertEqual(cppstd_default("gcc", "8.1", None, None), "gnu14")

    def test_clang_cppstd_flags(self):
        self.assertEqual(cppstd_flag("clang", "2.0", "98"), None)
        self.assertEqual(cppstd_flag("clang", "2.0", "gnu98"), None)
        self.assertEqual(cppstd_flag("clang", "2.0", "11"), None)
        self.assertEqual(cppstd_flag("clang", "2.0", "14"), None)

        self.assertEqual(cppstd_flag("clang", "2.1", "98"), "-std=c++98")
        self.assertEqual(cppstd_flag("clang", "2.1", "gnu98"), "-std=gnu++98")
        self.assertEqual(cppstd_flag("clang", "2.1", "11"), "-std=c++0x")
        self.assertEqual(cppstd_flag("clang", "2.1", "14"), None)

        self.assertEqual(cppstd_flag("clang", "3.0", "11"), '-std=c++0x')
        self.assertEqual(cppstd_flag("clang", "3.0", "14"), None)

        self.assertEqual(cppstd_flag("clang", "3.1", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("clang", "3.1", "14"), None)

        self.assertEqual(cppstd_flag("clang", "3.4", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("clang", "3.4", "14"), '-std=c++1y')
        self.assertEqual(cppstd_flag("clang", "3.4", "17"), None)

        self.assertEqual(cppstd_flag("clang", "3.5", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("clang", "3.5", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("clang", "3.5", "17"), '-std=c++1z')

        self.assertEqual(cppstd_flag("clang", "5", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("clang", "5", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("clang", "5", "gnu14"), '-std=gnu++14')
        self.assertEqual(cppstd_flag("clang", "5", "17"), '-std=c++17')

        self.assertEqual(cppstd_flag("clang", "5.1", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("clang", "5.1", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("clang", "5.1", "17"), '-std=c++17')

        self.assertEqual(cppstd_flag("clang", "6", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("clang", "6", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("clang", "6", "17"), '-std=c++17')
        self.assertEqual(cppstd_flag("clang", "6", "20"), '-std=c++2a')

        self.assertEqual(cppstd_flag("clang", "7", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("clang", "7", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("clang", "7", "17"), '-std=c++17')
        self.assertEqual(cppstd_flag("clang", "7", "20"), '-std=c++2a')

        self.assertEqual(cppstd_flag("clang", "8", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("clang", "8", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("clang", "8", "17"), '-std=c++17')
        self.assertEqual(cppstd_flag("clang", "8", "20"), '-std=c++2a')

    def test_clang_cppstd_defaults(self):
        self.assertEqual(cppstd_default("clang", "2", None, None), "gnu98")
        self.assertEqual(cppstd_default("clang", "2.1", None, None), "gnu98")
        self.assertEqual(cppstd_default("clang", "3.0", None, None), "gnu98")
        self.assertEqual(cppstd_default("clang", "3.1", None, None), "gnu98")
        self.assertEqual(cppstd_default("clang", "3.4", None, None), "gnu98")
        self.assertEqual(cppstd_default("clang", "3.5", None, None), "gnu98")
        self.assertEqual(cppstd_default("clang", "5", None, None), "gnu98")
        self.assertEqual(cppstd_default("clang", "5.1", None, None), "gnu98")
        self.assertEqual(cppstd_default("clang", "6", None, None), "gnu14")
        self.assertEqual(cppstd_default("clang", "7", None, None), "gnu14")

    def test_apple_clang_cppstd_flags(self):
        self.assertEqual(cppstd_flag("apple-clang", "3.9", "98"), None)
        self.assertEqual(cppstd_flag("apple-clang", "3.9", "gnu98"), None)
        self.assertEqual(cppstd_flag("apple-clang", "3.9", "11"), None)
        self.assertEqual(cppstd_flag("apple-clang", "3.9", "14"), None)

        self.assertEqual(cppstd_flag("apple-clang", "4.0", "98"), "-std=c++98")
        self.assertEqual(cppstd_flag("apple-clang", "4.0", "gnu98"), "-std=gnu++98")
        self.assertEqual(cppstd_flag("apple-clang", "4.0", "11"), "-std=c++11")
        self.assertEqual(cppstd_flag("apple-clang", "4.0", "14"), None)

        self.assertEqual(cppstd_flag("apple-clang", "5.0", "98"), "-std=c++98")
        self.assertEqual(cppstd_flag("apple-clang", "5.0", "gnu98"), "-std=gnu++98")
        self.assertEqual(cppstd_flag("apple-clang", "5.0", "11"), "-std=c++11")
        self.assertEqual(cppstd_flag("apple-clang", "5.0", "14"), None)

        self.assertEqual(cppstd_flag("apple-clang", "5.1", "98"), "-std=c++98")
        self.assertEqual(cppstd_flag("apple-clang", "5.1", "gnu98"), "-std=gnu++98")
        self.assertEqual(cppstd_flag("apple-clang", "5.1", "11"), "-std=c++11")
        self.assertEqual(cppstd_flag("apple-clang", "5.1", "14"), "-std=c++1y")

        self.assertEqual(cppstd_flag("apple-clang", "6.1", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("apple-clang", "6.1", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("apple-clang", "6.1", "17"), "-std=c++1z")

        self.assertEqual(cppstd_flag("apple-clang", "7", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("apple-clang", "7", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("apple-clang", "7", "17"), "-std=c++1z")

        self.assertEqual(cppstd_flag("apple-clang", "8", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("apple-clang", "8", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("apple-clang", "8", "17"), "-std=c++1z")

        self.assertEqual(cppstd_flag("apple-clang", "9", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("apple-clang", "9", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("apple-clang", "9", "17"), "-std=c++1z")

        self.assertEqual(cppstd_flag("apple-clang", "9.1", "11"), '-std=c++11')
        self.assertEqual(cppstd_flag("apple-clang", "9.1", "14"), '-std=c++14')
        self.assertEqual(cppstd_flag("apple-clang", "9.1", "17"), "-std=c++17")

        self.assertEqual(cppstd_flag("apple-clang", "10.0", "17"), "-std=c++17")
        self.assertEqual(cppstd_flag("apple-clang", "11.0", "17"), "-std=c++17")

    def test_apple_clang_cppstd_defaults(self):
        self.assertEqual(cppstd_default("apple-clang", "2", None, None), "gnu98")
        self.assertEqual(cppstd_default("apple-clang", "3", None, None), "gnu98")
        self.assertEqual(cppstd_default("apple-clang", "4", None, None), "gnu98")
        self.assertEqual(cppstd_default("apple-clang", "5", None, None), "gnu98")
        self.assertEqual(cppstd_default("apple-clang", "6", None, None), "gnu98")
        self.assertEqual(cppstd_default("apple-clang", "7", None, None), "gnu98")
        self.assertEqual(cppstd_default("apple-clang", "8", None, None), "gnu98")
        self.assertEqual(cppstd_default("apple-clang", "9", None, None), "gnu98")
        self.assertEqual(cppstd_default("apple-clang", "10", None, None), "gnu98")
        self.assertEqual(cppstd_default("apple-clang", "11", None, None), "gnu98")

    def test_visual_cppstd_flags(self):
        self.assertEqual(cppstd_flag("Visual Studio", "12", "11"), None)
        self.assertEqual(cppstd_flag("Visual Studio", "12", "14"), None)
        self.assertEqual(cppstd_flag("Visual Studio", "12", "17"), None)

        self.assertEqual(cppstd_flag("Visual Studio", "14", "11"), None)
        self.assertEqual(cppstd_flag("Visual Studio", "14", "14"), '/std:c++14')
        self.assertEqual(cppstd_flag("Visual Studio", "14", "17"), '/std:c++latest')

        self.assertEqual(cppstd_flag("Visual Studio", "17", "11"), None)
        self.assertEqual(cppstd_flag("Visual Studio", "17", "14"), '/std:c++14')
        self.assertEqual(cppstd_flag("Visual Studio", "17", "17"), '/std:c++17')
        self.assertEqual(cppstd_flag("Visual Studio", "17", "20"), '/std:c++latest')

    def test_visual_cppstd_defaults(self):
        self.assertEqual(cppstd_default("Visual Studio", "11", None, None), None)
        self.assertEqual(cppstd_default("Visual Studio", "12", None, None), None)
        self.assertEqual(cppstd_default("Visual Studio", "13", None, None), None)
        self.assertEqual(cppstd_default("Visual Studio", "14", None, None), "14")
        self.assertEqual(cppstd_default("Visual Studio", "15", None, None), "14")

    def test_nvcc_cppstd_flags(self):
        self.assertEqual(cppstd_flag("nvcc", "6.5", "03"), None)
        self.assertEqual(cppstd_flag("nvcc", "6.5", "11"), "-std=c++11")
        self.assertEqual(cppstd_flag("nvcc", "6.5", "14"), None)

        self.assertEqual(cppstd_flag("nvcc", "7.0", "03"), None)
        self.assertEqual(cppstd_flag("nvcc", "7.0", "11"), "-std=c++11")
        self.assertEqual(cppstd_flag("nvcc", "7.0", "14"), None)

        self.assertEqual(cppstd_flag("nvcc", "7.5", "03"), None)
        self.assertEqual(cppstd_flag("nvcc", "7.5", "11"), "-std=c++11")
        self.assertEqual(cppstd_flag("nvcc", "7.5", "14"), None)

        self.assertEqual(cppstd_flag("nvcc", "8.0", "03"), None)
        self.assertEqual(cppstd_flag("nvcc", "8.0", "11"), "-std=c++11")
        self.assertEqual(cppstd_flag("nvcc", "8.0", "14"), None)

        self.assertEqual(cppstd_flag("nvcc", "9.0", "03"), "-std=c++03")
        self.assertEqual(cppstd_flag("nvcc", "9.0", "11"), "-std=c++11")
        self.assertEqual(cppstd_flag("nvcc", "9.0", "14"), "-std=c++14")

        self.assertEqual(cppstd_flag("nvcc", "9.1", "03"), "-std=c++03")
        self.assertEqual(cppstd_flag("nvcc", "9.1", "11"), "-std=c++11")
        self.assertEqual(cppstd_flag("nvcc", "9.1", "14"), "-std=c++14")

        self.assertEqual(cppstd_flag("nvcc", "9.2", "03"), "-std=c++03")
        self.assertEqual(cppstd_flag("nvcc", "9.2", "11"), "-std=c++11")
        self.assertEqual(cppstd_flag("nvcc", "9.2", "14"), "-std=c++14")

        self.assertEqual(cppstd_flag("nvcc", "10.0", "03"), "-std=c++03")
        self.assertEqual(cppstd_flag("nvcc", "10.0", "11"), "-std=c++11")
        self.assertEqual(cppstd_flag("nvcc", "10.0", "14"), "-std=c++14")

        self.assertEqual(cppstd_flag("nvcc", "10.1", "03"), "-std=c++03")
        self.assertEqual(cppstd_flag("nvcc", "10.1", "11"), "-std=c++11")
        self.assertEqual(cppstd_flag("nvcc", "10.1", "14"), "-std=c++14")

        self.assertEqual(cppstd_flag("nvcc", "10.2", "03"), "-std=c++03")
        self.assertEqual(cppstd_flag("nvcc", "10.2", "11"), "-std=c++11")
        self.assertEqual(cppstd_flag("nvcc", "10.2", "14"), "-std=c++14")

    def test_nvcc_cppstd_defaults(self):
        self.assertEqual(cppstd_default("nvcc", None, "gcc", "4.8"), "gnu98")
        self.assertEqual(cppstd_default("nvcc", None, "gcc", "5"), "gnu98")
        self.assertEqual(cppstd_default("nvcc", None, "gcc", "6"), "gnu14")
        self.assertEqual(cppstd_default("nvcc", None, "gcc", "6.1"), "gnu14")
        self.assertEqual(cppstd_default("nvcc", None, "gcc", "7.3"), "gnu14")
        self.assertEqual(cppstd_default("nvcc", None, "gcc", "8.1"), "gnu14")
        self.assertEqual(cppstd_default("nvcc", None, "clang", "5"), "gnu98")
        self.assertEqual(cppstd_default("nvcc", None, "clang", "6"), "gnu14")
        self.assertEqual(cppstd_default("nvcc", None, "clang", "7"), "gnu14")
        self.assertEqual(cppstd_default("nvcc", None, "Visual Studio", "13"), None)
        self.assertEqual(cppstd_default("nvcc", None, "Visual Studio", "14"), "14")
        self.assertEqual(cppstd_default("nvcc", None, "Visual Studio", "15"), "14")
        self.assertEqual(cppstd_default("nvcc", None, "Visual Studio", "16"), "14")