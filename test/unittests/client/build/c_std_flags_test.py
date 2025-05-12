import unittest

from conan.internal.api.detect.detect_api import default_cstd
from conan.tools.build.flags import cstd_flag
from conan.internal.model.version import Version
from conan.test.utils.mocks import MockSettings, ConanFileMock


def _make_cstd_flag(compiler, compiler_version, cstd=None):
    conanfile = ConanFileMock()
    conanfile.settings = MockSettings({"compiler": compiler,
                                       "compiler.version": compiler_version,
                                       "compiler.cstd": cstd})
    return cstd_flag(conanfile)


def _make_cstd_default(compiler, compiler_version):
    return default_cstd(compiler, Version(compiler_version))


class CompilerFlagsTest(unittest.TestCase):

    def test_gcc_cstd_flags(self):
        self.assertEqual(_make_cstd_flag("gcc", "4.2", "99"), "-std=c99")
        self.assertEqual(_make_cstd_flag("gcc", "4.2", "gnu99"), "-std=gnu99")
        self.assertEqual(_make_cstd_flag("gcc", "4.2", "11"), "-std=c11")
        # self.assertEqual(_make_cstd_flag("gcc", "4.2", "11"), None)

        self.assertEqual(_make_cstd_flag("gcc", "4.3", "11"), "-std=c11")
        # self.assertEqual(_make_cstd_flag("gcc", "4.3", "11"), None)

        self.assertEqual(_make_cstd_flag("gcc", "4.6", "11"), "-std=c11")
        self.assertEqual(_make_cstd_flag("gcc", "4.6", "gnu11"), "-std=gnu11")
        # self.assertEqual(_make_cstd_flag("gcc", "4.6", "11"), "-std=c1x")
        # self.assertEqual(_make_cstd_flag("gcc", "4.6", "gnu11"), "-std=gnu1x")

        self.assertEqual(_make_cstd_flag("gcc", "4.7", "11"), "-std=c11")
        self.assertEqual(_make_cstd_flag("gcc", "4.7", "gnu11"), "-std=gnu11")

        self.assertEqual(_make_cstd_flag("gcc", "4.8", "11"), "-std=c11")
        self.assertEqual(_make_cstd_flag("gcc", "4.8", "gnu11"), "-std=gnu11")
        self.assertEqual(_make_cstd_flag("gcc", "4.8", "17"), "-std=c17")
        # self.assertEqual(_make_cstd_flag("gcc", "4.8", "17"), None)

        self.assertEqual(_make_cstd_flag("gcc", "4.9", "11"), "-std=c11")
        self.assertEqual(_make_cstd_flag("gcc", "4.9", "gnu11"), "-std=gnu11")
        self.assertEqual(_make_cstd_flag("gcc", "4.9", "17"), "-std=c17")
        # self.assertEqual(_make_cstd_flag("gcc", "4.9", "17"), None)

        self.assertEqual(_make_cstd_flag("gcc", "5", "11"), "-std=c11")
        self.assertEqual(_make_cstd_flag("gcc", "5", "gnu11"), "-std=gnu11")
        self.assertEqual(_make_cstd_flag("gcc", "5", "17"), "-std=c17")
        # self.assertEqual(_make_cstd_flag("gcc", "5", "17"), None)

        self.assertEqual(_make_cstd_flag("gcc", "5.1", "11"), "-std=c11")
        self.assertEqual(_make_cstd_flag("gcc", "5.1", "gnu11"), "-std=gnu11")
        self.assertEqual(_make_cstd_flag("gcc", "5.1", "17"), "-std=c17")
        # self.assertEqual(_make_cstd_flag("gcc", "5.1", "17"), None)

        self.assertEqual(_make_cstd_flag("gcc", "7", "11"), "-std=c11")
        self.assertEqual(_make_cstd_flag("gcc", "7", "gnu11"), "-std=gnu11")
        self.assertEqual(_make_cstd_flag("gcc", "7", "17"), "-std=c17")
        # self.assertEqual(_make_cstd_flag("gcc", "7", "17"), None)

        self.assertEqual(_make_cstd_flag("gcc", "8", "11"), "-std=c11")
        self.assertEqual(_make_cstd_flag("gcc", "8", "gnu11"), "-std=gnu11")
        self.assertEqual(_make_cstd_flag("gcc", "8", "17"), "-std=c17")
        self.assertEqual(_make_cstd_flag("gcc", "8", "gnu17"), "-std=gnu17")
        self.assertEqual(_make_cstd_flag("gcc", "8", "23"), "-std=c23")
        # self.assertEqual(_make_cstd_flag("gcc", "8", "23"), None)

        self.assertEqual(_make_cstd_flag("gcc", "9", "11"), "-std=c11")
        self.assertEqual(_make_cstd_flag("gcc", "9", "gnu11"), "-std=gnu11")
        self.assertEqual(_make_cstd_flag("gcc", "9", "17"), "-std=c17")
        self.assertEqual(_make_cstd_flag("gcc", "9", "gnu17"), "-std=gnu17")
        self.assertEqual(_make_cstd_flag("gcc", "9", "23"), "-std=c23")
        self.assertEqual(_make_cstd_flag("gcc", "9", "gnu23"), "-std=gnu23")

        self.assertEqual(_make_cstd_flag("gcc", "11", "11"), "-std=c11")
        self.assertEqual(_make_cstd_flag("gcc", "11", "gnu11"), "-std=gnu11")
        self.assertEqual(_make_cstd_flag("gcc", "11", "17"), "-std=c17")
        self.assertEqual(_make_cstd_flag("gcc", "11", "gnu17"), "-std=gnu17")
        self.assertEqual(_make_cstd_flag("gcc", "11", "23"), "-std=c23")
        self.assertEqual(_make_cstd_flag("gcc", "11", "gnu23"), "-std=gnu23")

    def test_gcc_cstd_defaults(self):
        self.assertEqual(_make_cstd_default("gcc", "4"), "gnu99")
        self.assertEqual(_make_cstd_default("gcc", "5"), "gnu11")
        self.assertEqual(_make_cstd_default("gcc", "6"), "gnu11")
        self.assertEqual(_make_cstd_default("gcc", "6.1"), "gnu11")
        self.assertEqual(_make_cstd_default("gcc", "7.3"), "gnu11")
        self.assertEqual(_make_cstd_default("gcc", "8.1"), "gnu17")
        self.assertEqual(_make_cstd_default("gcc", "11"), "gnu17")
        self.assertEqual(_make_cstd_default("gcc", "11.1"), "gnu17")
        self.assertEqual(_make_cstd_default("gcc", "15.1"), "gnu23")

    def test_clang_cppstd_flags(self):
        self.assertEqual(_make_cstd_flag("clang", "3.0", "11"), '-std=c11')
        self.assertEqual(_make_cstd_flag("clang", "3.0", "17"), '-std=c17')
        # self.assertEqual(_make_cstd_flag("clang", "3.0", "17"), None)

        self.assertEqual(_make_cstd_flag("clang", "3.1", "11"), '-std=c11')
        self.assertEqual(_make_cstd_flag("clang", "3.1", "gnu11"), '-std=gnu11')
        self.assertEqual(_make_cstd_flag("clang", "3.1", "17"), '-std=c17')
        # self.assertEqual(_make_cstd_flag("clang", "3.1", "17"), None)

        self.assertEqual(_make_cstd_flag("clang", "3.4", "11"), '-std=c11')
        self.assertEqual(_make_cstd_flag("clang", "3.4", "gnu11"), '-std=gnu11')
        # self.assertEqual(_make_cstd_flag("clang", "3.4", "17"), None)
        self.assertEqual(_make_cstd_flag("clang", "3.4", "17"), '-std=c17')

        self.assertEqual(_make_cstd_flag("clang", "3.5", "11"), '-std=c11')
        self.assertEqual(_make_cstd_flag("clang", "3.5", "gnu11"), '-std=gnu11')
        self.assertEqual(_make_cstd_flag("clang", "3.5", "17"), '-std=c17')
        # self.assertEqual(_make_cstd_flag("clang", "3.5", "17"), None)

        self.assertEqual(_make_cstd_flag("clang", "5", "11"), '-std=c11')
        self.assertEqual(_make_cstd_flag("clang", "5", "gnu11"), '-std=gnu11')
        self.assertEqual(_make_cstd_flag("clang", "5", "17"), '-std=c17')
        # self.assertEqual(_make_cstd_flag("clang", "5", "17"), None)

        for version in ["6", "7", "8"]:
            self.assertEqual(_make_cstd_flag("clang", version, "11"), '-std=c11')
            self.assertEqual(_make_cstd_flag("clang", version, "17"), '-std=c17')
            self.assertEqual(_make_cstd_flag("clang", version, "gnu11"), '-std=gnu11')
            self.assertEqual(_make_cstd_flag("clang", version, "gnu17"), '-std=gnu17')
            self.assertEqual(_make_cstd_flag("clang", version, "23"), '-std=c23')
            # self.assertEqual(_make_cstd_flag("clang", version, "23"), None)

        self.assertEqual(_make_cstd_flag("clang", "9", "11"), '-std=c11')
        self.assertEqual(_make_cstd_flag("clang", "9", "17"), '-std=c17')
        self.assertEqual(_make_cstd_flag("clang", "9", "gnu11"), '-std=gnu11')
        self.assertEqual(_make_cstd_flag("clang", "9", "gnu17"), '-std=gnu17')
        self.assertEqual(_make_cstd_flag("clang", "9", "23"), '-std=c23')
        self.assertEqual(_make_cstd_flag("clang", "9", "gnu23"), '-std=gnu23')
        # self.assertEqual(_make_cstd_flag("clang", "9", "23"), '-std=c2x')
        # self.assertEqual(_make_cstd_flag("clang", "9", "gnu23"), '-std=gnu2x')

        self.assertEqual(_make_cstd_flag("clang", "18", "11"), '-std=c11')
        self.assertEqual(_make_cstd_flag("clang", "18", "17"), '-std=c17')
        self.assertEqual(_make_cstd_flag("clang", "18", "gnu11"), '-std=gnu11')
        self.assertEqual(_make_cstd_flag("clang", "18", "gnu17"), '-std=gnu17')
        self.assertEqual(_make_cstd_flag("clang", "18", "23"), '-std=c23')
        self.assertEqual(_make_cstd_flag("clang", "18", "gnu23"), '-std=gnu23')


    def test_clang_cppstd_defaults(self):
        self.assertEqual(_make_cstd_default("clang", "2"), "gnu99")
        self.assertEqual(_make_cstd_default("clang", "2.1"), "gnu99")
        self.assertEqual(_make_cstd_default("clang", "3.0"), "gnu99")
        self.assertEqual(_make_cstd_default("clang", "3.1"), "gnu99")
        self.assertEqual(_make_cstd_default("clang", "3.4"), "gnu99")
        self.assertEqual(_make_cstd_default("clang", "3.5"), "gnu99")
        self.assertEqual(_make_cstd_default("clang", "5"), "gnu11")
        self.assertEqual(_make_cstd_default("clang", "5.1"), "gnu11")
        self.assertEqual(_make_cstd_default("clang", "6"), "gnu11")
        self.assertEqual(_make_cstd_default("clang", "7"), "gnu11")
        self.assertEqual(_make_cstd_default("clang", "8"), "gnu11")
        self.assertEqual(_make_cstd_default("clang", "9"), "gnu11")
        self.assertEqual(_make_cstd_default("clang", "10"), "gnu11")
        self.assertEqual(_make_cstd_default("clang", "11"), "gnu17")
        self.assertEqual(_make_cstd_default("clang", "12"), "gnu17")
        self.assertEqual(_make_cstd_default("clang", "13"), "gnu17")
        self.assertEqual(_make_cstd_default("clang", "14"), "gnu17")
        self.assertEqual(_make_cstd_default("clang", "15"), "gnu17")
        self.assertEqual(_make_cstd_default("clang", "16"), "gnu17")
        self.assertEqual(_make_cstd_default("clang", "17"), "gnu17")
        self.assertEqual(_make_cstd_default("clang", "18"), "gnu17")
        self.assertEqual(_make_cstd_default("clang", "19"), "gnu17")
        self.assertEqual(_make_cstd_default("clang", "20"), "gnu17")
