import unittest

from conans.client.build.cppstd_flags import cppstd_default
from conans.test.utils.mocks import MockSettings
from conans.tools import cppstd_flag


def _make_cppstd_flag(compiler, compiler_version, cppstd=None, compiler_base=None):
    settings = MockSettings({"compiler": compiler,
                             "compiler.version": compiler_version,
                             "compiler.cppstd": cppstd})
    if compiler_base:
        settings.values["compiler.base"] = compiler_base
    return cppstd_flag(settings)


def _make_cppstd_default(compiler, compiler_version, compiler_base=None):
    settings = MockSettings({"compiler": compiler,
                             "compiler.version": compiler_version})
    if compiler_base:
        settings.values["compiler.base"] = compiler_base
    return cppstd_default(settings)


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

    def test_visual_cppstd_flags(self):
        self.assertEqual(_make_cppstd_flag("Visual Studio", "12", "11"), None)
        self.assertEqual(_make_cppstd_flag("Visual Studio", "12", "14"), None)
        self.assertEqual(_make_cppstd_flag("Visual Studio", "12", "17"), None)

        self.assertEqual(_make_cppstd_flag("Visual Studio", "14", "11"), None)
        self.assertEqual(_make_cppstd_flag("Visual Studio", "14", "14"), '/std:c++14')
        self.assertEqual(_make_cppstd_flag("Visual Studio", "14", "17"), '/std:c++latest')

        self.assertEqual(_make_cppstd_flag("Visual Studio", "17", "11"), None)
        self.assertEqual(_make_cppstd_flag("Visual Studio", "17", "14"), '/std:c++14')
        self.assertEqual(_make_cppstd_flag("Visual Studio", "17", "17"), '/std:c++17')
        self.assertEqual(_make_cppstd_flag("Visual Studio", "17", "20"), '/std:c++20')
        self.assertEqual(_make_cppstd_flag("Visual Studio", "17", "23"), '/std:c++latest')

    def test_visual_cppstd_defaults(self):
        self.assertEqual(_make_cppstd_default("Visual Studio", "11"), None)
        self.assertEqual(_make_cppstd_default("Visual Studio", "12"), None)
        self.assertEqual(_make_cppstd_default("Visual Studio", "13"), None)
        self.assertEqual(_make_cppstd_default("Visual Studio", "14"), "14")
        self.assertEqual(_make_cppstd_default("Visual Studio", "15"), "14")

    def test_intel_visual_cppstd_defaults(self):
        self.assertEqual(_make_cppstd_default("intel", "19", "Visual Studio"), None)

    def test_intel_gcc_cppstd_defaults(self):
        self.assertEqual(_make_cppstd_default("intel", "19", "gcc"), 'gnu98')

    def test_intel_visual_cppstd_flag(self):
        self.assertEqual(_make_cppstd_flag("intel", "19.1", "gnu98", "Visual Studio"), None)
        self.assertEqual(_make_cppstd_flag("intel", "19.1", "11", "Visual Studio"), '/Qstd=c++11')
        self.assertEqual(_make_cppstd_flag("intel", "19.1", "14", "Visual Studio"), '/Qstd=c++14')
        self.assertEqual(_make_cppstd_flag("intel", "19.1", "17", "Visual Studio"), '/Qstd=c++17')
        self.assertEqual(_make_cppstd_flag("intel", "19.1", "20", "Visual Studio"), '/Qstd=c++20')

        self.assertEqual(_make_cppstd_flag("intel", "19", "gnu98", "Visual Studio"), None)
        self.assertEqual(_make_cppstd_flag("intel", "19", "11", "Visual Studio"), '/Qstd=c++11')
        self.assertEqual(_make_cppstd_flag("intel", "19", "14", "Visual Studio"), '/Qstd=c++14')
        self.assertEqual(_make_cppstd_flag("intel", "19", "17", "Visual Studio"), '/Qstd=c++17')
        self.assertEqual(_make_cppstd_flag("intel", "19", "20", "Visual Studio"), None)

        self.assertEqual(_make_cppstd_flag("intel", "17", "gnu98", "Visual Studio"), None)
        self.assertEqual(_make_cppstd_flag("intel", "17", "11", "Visual Studio"), '/Qstd=c++11')
        self.assertEqual(_make_cppstd_flag("intel", "17", "14", "Visual Studio"), '/Qstd=c++14')
        self.assertEqual(_make_cppstd_flag("intel", "17", "17", "Visual Studio"), None)
        self.assertEqual(_make_cppstd_flag("intel", "17", "20", "Visual Studio"), None)

        self.assertEqual(_make_cppstd_flag("intel", "15", "gnu98", "Visual Studio"), None)
        self.assertEqual(_make_cppstd_flag("intel", "15", "11", "Visual Studio"), '/Qstd=c++11')
        self.assertEqual(_make_cppstd_flag("intel", "15", "14", "Visual Studio"), None)
        self.assertEqual(_make_cppstd_flag("intel", "15", "17", "Visual Studio"), None)
        self.assertEqual(_make_cppstd_flag("intel", "15", "20", "Visual Studio"), None)

        self.assertEqual(_make_cppstd_flag("intel", "12", "gnu98", "Visual Studio"), None)
        self.assertEqual(_make_cppstd_flag("intel", "12", "11", "Visual Studio"), '/Qstd=c++0x')
        self.assertEqual(_make_cppstd_flag("intel", "12", "14", "Visual Studio"), None)
        self.assertEqual(_make_cppstd_flag("intel", "12", "17", "Visual Studio"), None)
        self.assertEqual(_make_cppstd_flag("intel", "12", "20", "Visual Studio"), None)

        self.assertEqual(_make_cppstd_flag("intel", "11", "gnu98", "Visual Studio"), None)
        self.assertEqual(_make_cppstd_flag("intel", "11", "11", "Visual Studio"), None)
        self.assertEqual(_make_cppstd_flag("intel", "11", "14", "Visual Studio"), None)
        self.assertEqual(_make_cppstd_flag("intel", "11", "17", "Visual Studio"), None)
        self.assertEqual(_make_cppstd_flag("intel", "11", "20", "Visual Studio"), None)

    def test_intel_gcc_cppstd_flag(self):
        self.assertEqual(_make_cppstd_flag("intel", "19.1", "gnu98", "gcc"), '-std=gnu++98')
        self.assertEqual(_make_cppstd_flag("intel", "19.1", "11", "gcc"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("intel", "19.1", "14", "gcc"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("intel", "19.1", "17", "gcc"), '-std=c++17')
        self.assertEqual(_make_cppstd_flag("intel", "19.1", "20", "gcc"), '-std=c++20')

        self.assertEqual(_make_cppstd_flag("intel", "19", "gnu98", "gcc"), '-std=gnu++98')
        self.assertEqual(_make_cppstd_flag("intel", "19", "11", "gcc"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("intel", "19", "14", "gcc"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("intel", "19", "17", "gcc"), '-std=c++17')
        self.assertEqual(_make_cppstd_flag("intel", "19", "20", "gcc"), None)

        self.assertEqual(_make_cppstd_flag("intel", "17", "gnu98", "gcc"), '-std=gnu++98')
        self.assertEqual(_make_cppstd_flag("intel", "17", "11", "gcc"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("intel", "17", "14", "gcc"), '-std=c++14')
        self.assertEqual(_make_cppstd_flag("intel", "17", "17", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("intel", "17", "20", "gcc"), None)

        self.assertEqual(_make_cppstd_flag("intel", "15", "gnu98", "gcc"), '-std=gnu++98')
        self.assertEqual(_make_cppstd_flag("intel", "15", "11", "gcc"), '-std=c++11')
        self.assertEqual(_make_cppstd_flag("intel", "15", "14", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("intel", "15", "17", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("intel", "15", "20", "gcc"), None)

        self.assertEqual(_make_cppstd_flag("intel", "12", "gnu98", "gcc"), '-std=gnu++98')
        self.assertEqual(_make_cppstd_flag("intel", "12", "11", "gcc"), '-std=c++0x')
        self.assertEqual(_make_cppstd_flag("intel", "12", "14", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("intel", "12", "17", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("intel", "12", "20", "gcc"), None)

        self.assertEqual(_make_cppstd_flag("intel", "11", "gnu98", "gcc"), '-std=gnu++98')
        self.assertEqual(_make_cppstd_flag("intel", "11", "11", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("intel", "11", "14", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("intel", "11", "17", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("intel", "11", "20", "gcc"), None)

    def test_mcst_lcc_cppstd_defaults(self):
        self.assertEqual(_make_cppstd_default("mcst-lcc", "1.19", "gcc"), "gnu98")
        self.assertEqual(_make_cppstd_default("mcst-lcc", "1.20", "gcc"), "gnu98")
        self.assertEqual(_make_cppstd_default("mcst-lcc", "1.21", "gcc"), "gnu98")
        self.assertEqual(_make_cppstd_default("mcst-lcc", "1.22", "gcc"), "gnu98")
        self.assertEqual(_make_cppstd_default("mcst-lcc", "1.23", "gcc"), "gnu98")
        self.assertEqual(_make_cppstd_default("mcst-lcc", "1.24", "gcc"), "gnu14")
        self.assertEqual(_make_cppstd_default("mcst-lcc", "1.25", "gcc"), "gnu14")

    def test_mcst_lcc_cppstd_flag(self):
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.19", "98", "gcc"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.19", "11", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.19", "14", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.19", "17", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.19", "20", "gcc"), None)

        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.20", "98", "gcc"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.20", "11", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.20", "14", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.20", "17", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.20", "20", "gcc"), None)

        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.21", "98", "gcc"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.21", "11", "gcc"), "-std=c++11")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.21", "14", "gcc"), "-std=c++14")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.21", "17", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.21", "20", "gcc"), None)

        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.22", "98", "gcc"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.22", "11", "gcc"), "-std=c++11")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.22", "14", "gcc"), "-std=c++14")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.22", "17", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.22", "20", "gcc"), None)

        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.23", "98", "gcc"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.23", "11", "gcc"), "-std=c++11")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.23", "14", "gcc"), "-std=c++14")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.23", "17", "gcc"), None)
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.23", "20", "gcc"), None)

        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.24", "98", "gcc"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.24", "11", "gcc"), "-std=c++11")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.24", "14", "gcc"), "-std=c++14")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.24", "17", "gcc"), "-std=c++17")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.24", "20", "gcc"), None)

        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.25", "98", "gcc"), "-std=c++98")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.25", "11", "gcc"), "-std=c++11")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.25", "14", "gcc"), "-std=c++14")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.25", "17", "gcc"), "-std=c++17")
        self.assertEqual(_make_cppstd_flag("mcst-lcc", "1.25", "20", "gcc"), "-std=c++2a")
