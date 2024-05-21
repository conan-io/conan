import unittest

from conan.internal.api.detect_api import default_cppstd
from conan.tools.build import cppstd_flag
from conans.model.version import Version
from conan.test.utils.mocks import MockSettings, ConanFileMock


def _make_cppstd_flag(compiler, compiler_version, cppstd=None):
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": compiler,
                             "compiler.version": compiler_version,
                             "compiler.cppstd": cppstd})
    return cppstd_flag(conanfile)


def _make_cppstd_default(compiler, compiler_version):
    return default_cppstd(compiler, Version(compiler_version))


class CompilerFlagsTest(unittest.TestCase):

    def test_gcc_cppstd_flags(self):
        self.assertEqual(_make_cppstd_flag("gcc", "4.2", "98"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("gcc", "4.2", "gnu98"), "-std=gnu++98")
        self.assertEqual(_make_cppstd_flag("gcc", "4.2", "11"), None)
        self.assertEqual(_make_cppstd_flag("gcc", "4.2", "14"), None)

        self.assertEqual(_make_cppstd_flag("gcc", "4.3", "98"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("gcc", "4.3", "gnu98"), "-std=gnu++98")
        self.assertEqual(_make_cppstd_flag("gcc", "4.3", "11"), "-std=c++0x")
        self.assertEqual(_make_cppstd_flag("gcc", "4.3", "14"), None)

        self.assertEqual(_make_cppstd_flag("gcc", "4.6", "11"), '-std=c++0x')
        self.assertEqual(_make_cppstd_flag("gcc", "4.6", "14"), None)

        self.assertEqual(_make_cppstd_flag("gcc", "4.7", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("gcc", "4.7", "14"), None)

        self.assertEqual(_make_cppstd_flag("gcc", "4.8", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("gcc", "4.8", "14"), '-std=c++1y')
        self.assertEqual(_make_cppstd_flag("gcc", "4.8", "17"), None)

        self.assertEqual(_make_cppstd_flag("gcc", "4.9", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("gcc", "4.9", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("gcc", "4.9", "17"), None)

        self.assertEqual(_make_cppstd_flag("gcc", "5", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("gcc", "5", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("gcc", "5", "gnu14"), '-std=gnu++14')
        self.assertEqual(_make_cppstd_flag("gcc", "5", "17"), '-std=c++1z')
        self.assertEqual(_make_cppstd_flag("gcc", "5", "gnu17"), '-std=gnu++1z')

        self.assertEqual(_make_cppstd_flag("gcc", "5.1", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("gcc", "5.1", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("gcc", "5.1", "17"), '-std=c++1z')

        self.assertEqual(_make_cppstd_flag("gcc", "7", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("gcc", "7", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("gcc", "7", "17"), '-std=c++17')

        self.assertEqual(_make_cppstd_flag("gcc", "8", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("gcc", "8", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("gcc", "8", "17"), '-std=c++17')
        self.assertEqual(_make_cppstd_flag("gcc", "8", "20"), '-std=c++2a')
        self.assertEqual(_make_cppstd_flag("gcc", "8", "23"), None)

        self.assertEqual(_make_cppstd_flag("gcc", "11", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("gcc", "11", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("gcc", "11", "17"), '-std=c++17')
        self.assertEqual(_make_cppstd_flag("gcc", "11", "20"), '-std=c++2a')
        self.assertEqual(_make_cppstd_flag("gcc", "11", "23"), '-std=c++2b')

    def test_gcc_cppstd_defaults(self):
        self.assertEqual(_make_cppstd_default("gcc", "4"), "gnu98")
        self.assertEqual(_make_cppstd_default("gcc", "5"), "gnu98")
        self.assertEqual(_make_cppstd_default("gcc", "6"), "gnu14")
        self.assertEqual(_make_cppstd_default("gcc", "6.1"), "gnu14")
        self.assertEqual(_make_cppstd_default("gcc", "7.3"), "gnu14")
        self.assertEqual(_make_cppstd_default("gcc", "8.1"), "gnu14")
        self.assertEqual(_make_cppstd_default("gcc", "11"), "gnu17")
        self.assertEqual(_make_cppstd_default("gcc", "11.1"), "gnu17")

    def test_clang_cppstd_flags(self):
        self.assertEqual(_make_cppstd_flag("clang", "2.0", "98"), None)
        self.assertEqual(_make_cppstd_flag("clang", "2.0", "gnu98"), None)
        self.assertEqual(_make_cppstd_flag("clang", "2.0", "11"), None)
        self.assertEqual(_make_cppstd_flag("clang", "2.0", "14"), None)

        self.assertEqual(_make_cppstd_flag("clang", "2.1", "98"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("clang", "2.1", "gnu98"), "-std=gnu++98")
        self.assertEqual(_make_cppstd_flag("clang", "2.1", "11"), "-std=c++0x")
        self.assertEqual(_make_cppstd_flag("clang", "2.1", "14"), None)

        self.assertEqual(_make_cppstd_flag("clang", "3.0", "11"), '-std=c++0x')
        self.assertEqual(_make_cppstd_flag("clang", "3.0", "14"), None)

        self.assertEqual(_make_cppstd_flag("clang", "3.1", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("clang", "3.1", "14"), None)

        self.assertEqual(_make_cppstd_flag("clang", "3.4", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("clang", "3.4", "14"), '-std=c++1y')
        self.assertEqual(_make_cppstd_flag("clang", "3.4", "17"), None)

        self.assertEqual(_make_cppstd_flag("clang", "3.5", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("clang", "3.5", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("clang", "3.5", "17"), '-std=c++1z')

        self.assertEqual(_make_cppstd_flag("clang", "5", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("clang", "5", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("clang", "5", "gnu14"), '-std=gnu++14')
        self.assertEqual(_make_cppstd_flag("clang", "5", "17"), '-std=c++17')

        self.assertEqual(_make_cppstd_flag("clang", "5.1", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("clang", "5.1", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("clang", "5.1", "17"), '-std=c++17')

        for version in ["6", "7", "8", "9", "10", "11"]:
            self.assertEqual(_make_cppstd_flag("clang", version, "11"), '-std=c++11')
            self.assertEqual(_make_cppstd_flag("clang", version, "14"), '-std=c++14')
            self.assertEqual(_make_cppstd_flag("clang", version, "17"), '-std=c++17')
            self.assertEqual(_make_cppstd_flag("clang", version, "20"), '-std=c++2a')

        self.assertEqual(_make_cppstd_flag("clang", "12", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("clang", "12", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("clang", "12", "17"), '-std=c++17')
        self.assertEqual(_make_cppstd_flag("clang", "12", "20"), '-std=c++20')
        self.assertEqual(_make_cppstd_flag("clang", "12", "23"), '-std=c++2b')

        self.assertEqual(_make_cppstd_flag("clang", "17", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("clang", "17", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("clang", "17", "17"), '-std=c++17')
        self.assertEqual(_make_cppstd_flag("clang", "17", "20"), '-std=c++20')
        self.assertEqual(_make_cppstd_flag("clang", "17", "23"), '-std=c++23')

    def test_clang_cppstd_defaults(self):
        self.assertEqual(_make_cppstd_default("clang", "2"), "gnu98")
        self.assertEqual(_make_cppstd_default("clang", "2.1"), "gnu98")
        self.assertEqual(_make_cppstd_default("clang", "3.0"), "gnu98")
        self.assertEqual(_make_cppstd_default("clang", "3.1"), "gnu98")
        self.assertEqual(_make_cppstd_default("clang", "3.4"), "gnu98")
        self.assertEqual(_make_cppstd_default("clang", "3.5"), "gnu98")
        self.assertEqual(_make_cppstd_default("clang", "5"), "gnu98")
        self.assertEqual(_make_cppstd_default("clang", "5.1"), "gnu98")
        self.assertEqual(_make_cppstd_default("clang", "6"), "gnu14")
        self.assertEqual(_make_cppstd_default("clang", "7"), "gnu14")
        self.assertEqual(_make_cppstd_default("clang", "8"), "gnu14")
        self.assertEqual(_make_cppstd_default("clang", "9"), "gnu14")
        self.assertEqual(_make_cppstd_default("clang", "10"), "gnu14")
        self.assertEqual(_make_cppstd_default("clang", "11"), "gnu14")
        self.assertEqual(_make_cppstd_default("clang", "12"), "gnu14")
        self.assertEqual(_make_cppstd_default("clang", "13"), "gnu14")
        self.assertEqual(_make_cppstd_default("clang", "14"), "gnu14")
        self.assertEqual(_make_cppstd_default("clang", "15"), "gnu14")
        self.assertEqual(_make_cppstd_default("clang", "16"), "gnu17")

    def test_apple_clang_cppstd_flags(self):
        self.assertEqual(_make_cppstd_flag("apple-clang", "3.9", "98"), None)
        self.assertEqual(_make_cppstd_flag("apple-clang", "3.9", "gnu98"), None)
        self.assertEqual(_make_cppstd_flag("apple-clang", "3.9", "11"), None)
        self.assertEqual(_make_cppstd_flag("apple-clang", "3.9", "14"), None)

        self.assertEqual(_make_cppstd_flag("apple-clang", "4.0", "98"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("apple-clang", "4.0", "gnu98"), "-std=gnu++98")
        self.assertEqual(_make_cppstd_flag("apple-clang", "4.0", "11"), "-std=c++11")
        self.assertEqual(_make_cppstd_flag("apple-clang", "4.0", "14"), None)

        self.assertEqual(_make_cppstd_flag("apple-clang", "5.0", "98"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("apple-clang", "5.0", "gnu98"), "-std=gnu++98")
        self.assertEqual(_make_cppstd_flag("apple-clang", "5.0", "11"), "-std=c++11")
        self.assertEqual(_make_cppstd_flag("apple-clang", "5.0", "14"), None)

        self.assertEqual(_make_cppstd_flag("apple-clang", "5.1", "98"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("apple-clang", "5.1", "gnu98"), "-std=gnu++98")
        self.assertEqual(_make_cppstd_flag("apple-clang", "5.1", "11"), "-std=c++11")
        self.assertEqual(_make_cppstd_flag("apple-clang", "5.1", "14"), "-std=c++1y")

        self.assertEqual(_make_cppstd_flag("apple-clang", "6.1", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("apple-clang", "6.1", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("apple-clang", "6.1", "17"), "-std=c++1z")

        self.assertEqual(_make_cppstd_flag("apple-clang", "7", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("apple-clang", "7", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("apple-clang", "7", "17"), "-std=c++1z")

        self.assertEqual(_make_cppstd_flag("apple-clang", "8", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("apple-clang", "8", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("apple-clang", "8", "17"), "-std=c++1z")

        self.assertEqual(_make_cppstd_flag("apple-clang", "9", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("apple-clang", "9", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("apple-clang", "9", "17"), "-std=c++1z")

        self.assertEqual(_make_cppstd_flag("apple-clang", "9.1", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("apple-clang", "9.1", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("apple-clang", "9.1", "17"), "-std=c++17")
        self.assertEqual(_make_cppstd_flag("apple-clang", "9.1", "20"), None)

        self.assertEqual(_make_cppstd_flag("apple-clang", "10.0", "17"), "-std=c++17")
        self.assertEqual(_make_cppstd_flag("apple-clang", "10.0", "20"), "-std=c++2a")
        self.assertEqual(_make_cppstd_flag("apple-clang", "11.0", "17"), "-std=c++17")
        self.assertEqual(_make_cppstd_flag("apple-clang", "11.0", "20"), "-std=c++2a")

        self.assertEqual(_make_cppstd_flag("apple-clang", "12.0", "17"), "-std=c++17")
        self.assertEqual(_make_cppstd_flag("apple-clang", "12.0", "20"), "-std=c++2a")
        self.assertEqual(_make_cppstd_flag("apple-clang", "12.0", "23"), None)

        self.assertEqual(_make_cppstd_flag("apple-clang", "13.0", "17"), "-std=c++17")
        self.assertEqual(_make_cppstd_flag("apple-clang", "13.0", "gnu17"), "-std=gnu++17")
        self.assertEqual(_make_cppstd_flag("apple-clang", "13.0", "20"), "-std=c++20")
        self.assertEqual(_make_cppstd_flag("apple-clang", "13.0", "gnu20"), "-std=gnu++20")
        self.assertEqual(_make_cppstd_flag("apple-clang", "13.0", "23"), "-std=c++2b")
        self.assertEqual(_make_cppstd_flag("apple-clang", "13.0", "gnu23"), "-std=gnu++2b")

        self.assertEqual(_make_cppstd_flag("apple-clang", "14.0", "17"), "-std=c++17")
        self.assertEqual(_make_cppstd_flag("apple-clang", "14.0", "gnu17"), "-std=gnu++17")
        self.assertEqual(_make_cppstd_flag("apple-clang", "14.0", "20"), "-std=c++20")
        self.assertEqual(_make_cppstd_flag("apple-clang", "14.0", "gnu20"), "-std=gnu++20")
        self.assertEqual(_make_cppstd_flag("apple-clang", "14.0", "23"), "-std=c++2b")
        self.assertEqual(_make_cppstd_flag("apple-clang", "14.0", "gnu23"), "-std=gnu++2b")

        self.assertEqual(_make_cppstd_flag("apple-clang", "15.0", "17"), "-std=c++17")
        self.assertEqual(_make_cppstd_flag("apple-clang", "15.0", "gnu17"), "-std=gnu++17")
        self.assertEqual(_make_cppstd_flag("apple-clang", "15.0", "20"), "-std=c++20")
        self.assertEqual(_make_cppstd_flag("apple-clang", "15.0", "gnu20"), "-std=gnu++20")
        self.assertEqual(_make_cppstd_flag("apple-clang", "15.0", "23"), "-std=c++2b")
        self.assertEqual(_make_cppstd_flag("apple-clang", "15.0", "gnu23"), "-std=gnu++2b")

    def test_apple_clang_cppstd_defaults(self):
        self.assertEqual(_make_cppstd_default("apple-clang", "2"), "gnu98")
        self.assertEqual(_make_cppstd_default("apple-clang", "3"), "gnu98")
        self.assertEqual(_make_cppstd_default("apple-clang", "4"), "gnu98")
        self.assertEqual(_make_cppstd_default("apple-clang", "5"), "gnu98")
        self.assertEqual(_make_cppstd_default("apple-clang", "6"), "gnu98")
        self.assertEqual(_make_cppstd_default("apple-clang", "7"), "gnu98")
        self.assertEqual(_make_cppstd_default("apple-clang", "8"), "gnu98")
        self.assertEqual(_make_cppstd_default("apple-clang", "9"), "gnu98")
        self.assertEqual(_make_cppstd_default("apple-clang", "10"), "gnu98")
        self.assertEqual(_make_cppstd_default("apple-clang", "11"), "gnu98")
        self.assertEqual(_make_cppstd_default("apple-clang", "12"), "gnu98")
        self.assertEqual(_make_cppstd_default("apple-clang", "13"), "gnu98")
        self.assertEqual(_make_cppstd_default("apple-clang", "14"), "gnu98")
        self.assertEqual(_make_cppstd_default("apple-clang", "15"), "gnu98")

    def test_visual_cppstd_flags(self):
        self.assertEqual(_make_cppstd_flag("msvc", "170", "11"), None)
        self.assertEqual(_make_cppstd_flag("msvc", "170", "14"), None)
        self.assertEqual(_make_cppstd_flag("msvc", "170", "17"), None)

        self.assertEqual(_make_cppstd_flag("msvc", "180", "11"), None)

        self.assertEqual(_make_cppstd_flag("msvc", "190", "14"), '/std:c++14')
        self.assertEqual(_make_cppstd_flag("msvc", "190", "17"), '/std:c++latest')

        self.assertEqual(_make_cppstd_flag("msvc", "191", "11"), None)
        self.assertEqual(_make_cppstd_flag("msvc", "191", "14"), '/std:c++14')
        self.assertEqual(_make_cppstd_flag("msvc", "191", "17"), '/std:c++17')
        self.assertEqual(_make_cppstd_flag("msvc", "191", "20"), '/std:c++latest')

        self.assertEqual(_make_cppstd_flag("msvc", "192", "17"), '/std:c++17')
        self.assertEqual(_make_cppstd_flag("msvc", "192", "20"), '/std:c++20')

        self.assertEqual(_make_cppstd_flag("msvc", "193", "20"), '/std:c++20')
        self.assertEqual(_make_cppstd_flag("msvc", "193", "23"), '/std:c++latest')

    def test_visual_cppstd_defaults(self):
        self.assertEqual(_make_cppstd_default("msvc", "170"), None)
        self.assertEqual(_make_cppstd_default("msvc", "180"), None)
        self.assertEqual(_make_cppstd_default("msvc", "190"), "14")
        self.assertEqual(_make_cppstd_default("msvc", "191"), "14")
        self.assertEqual(_make_cppstd_default("msvc", "192"), "14")
        self.assertEqual(_make_cppstd_default("msvc", "193"), "14")

    def test_intel_cppstd_flag(self):
        self.assertEqual(_make_cppstd_flag("intel-cc", "19.1", "gnu98"), '-std=gnu++98')
        self.assertEqual(_make_cppstd_flag("intel-cc", "19.1", "11"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("intel-cc", "19.1", "14"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("intel-cc", "19.1", "17"), '-std=c++17')
        self.assertEqual(_make_cppstd_flag("intel-cc", "19.1", "20"), '-std=c++20')

    def test_mcst_lcc_cppstd_defaults(self):
        self.assertEqual(_make_cppstd_default("mcst-lcc", "1.19"), "gnu98")
        self.assertEqual(_make_cppstd_default("mcst-lcc", "1.20"), "gnu98")
        self.assertEqual(_make_cppstd_default("mcst-lcc", "1.21"), "gnu98")
        self.assertEqual(_make_cppstd_default("mcst-lcc", "1.22"), "gnu98")
        self.assertEqual(_make_cppstd_default("mcst-lcc", "1.23"), "gnu98")
        self.assertEqual(_make_cppstd_default("mcst-lcc", "1.24"), "gnu14")
        self.assertEqual(_make_cppstd_default("mcst-lcc", "1.25"), "gnu14")

    def test_mcst_lcc_cppstd_flag(self):
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.19", "98"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.19", "11"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.19", "14"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.19", "17"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.19", "20"), None)

        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.20", "98"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.20", "11"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.20", "14"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.20", "17"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.20", "20"), None)

        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.21", "98"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.21", "11"), "-std=c++11")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.21", "14"), "-std=c++14")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.21", "17"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.21", "20"), None)

        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.22", "98"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.22", "11"), "-std=c++11")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.22", "14"), "-std=c++14")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.22", "17"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.22", "20"), None)

        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.23", "98"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.23", "11"), "-std=c++11")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.23", "14"), "-std=c++14")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.23", "17"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.23", "20"), None)

        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.24", "98"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.24", "11"), "-std=c++11")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.24", "14"), "-std=c++14")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.24", "17"), "-std=c++17")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.24", "20"), None)

        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.25", "98"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.25", "11"), "-std=c++11")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.25", "14"), "-std=c++14")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.25", "17"), "-std=c++17")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.25", "20"), "-std=c++2a")
