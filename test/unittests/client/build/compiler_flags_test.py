import unittest
from parameterized.parameterized import parameterized

from conan.tools.build.flags import architecture_flag, build_type_flags
from conan.test.utils.mocks import MockSettings


class CompilerFlagsTest(unittest.TestCase):

    @parameterized.expand([("gcc", "x86", None, "-m32"),
                           ("clang", "x86", None, "-m32"),
                           ("sun-cc", "x86", None, "-m32"),
                           ("gcc", "x86_64", None, "-m64"),
                           ("clang", "x86_64", None, "-m64"),
                           ("sun-cc", "x86_64", None, "-m64"),
                           ("sun-cc", "sparc", None, "-m32"),
                           ("sun-cc", "sparcv9", None, "-m64"),
                           ("gcc", "armv7", None, ""),
                           ("clang", "armv7", None, ""),
                           ("sun-cc", "armv7", None, ""),
                           ("gcc", "s390", None, "-m31"),
                           ("clang", "s390", None, "-m31"),
                           ("sun-cc", "s390", None, "-m31"),
                           ("gcc", "s390x", None, "-m64"),
                           ("clang", "s390x", None, "-m64"),
                           ("sun-cc", "s390x", None, "-m64"),
                           ("msvc", "x86", None, ""),
                           ("msvc", "x86_64", None, ""),
                           ("gcc", "ppc32", "AIX", "-maix32"),
                           ("gcc", "ppc64", "AIX", "-maix64"),
                           ])
    def test_arch_flag(self, compiler, arch, the_os, flag):
        settings = MockSettings({"compiler": compiler,
                                 "arch": arch,
                                 "os": the_os})
        self.assertEqual(architecture_flag(settings), flag)

    def test_catalyst(self):
        settings = MockSettings({"compiler": "apple-clang",
                                 "arch": "x86_64",
                                 "os": "Macos",
                                 "os.subsystem": "catalyst",
                                 "os.subsystem.ios_version": "13.1"})
        self.assertEqual(architecture_flag(settings), "--target=x86_64-apple-ios13.1-macabi")

        settings = MockSettings({"compiler": "apple-clang",
                                 "arch": "armv8",
                                 "os": "Macos",
                                 "os.subsystem": "catalyst",
                                 "os.subsystem.ios_version": "13.1"})
        self.assertEqual(architecture_flag(settings), "--target=arm64-apple-ios13.1-macabi")

    @parameterized.expand([("Linux", "x86", "-m32"),
                           ("Linux", "x86_64", "-m64"),
                           ("Windows", "x86", "/Qm32"),
                           ("Windows", "x86_64", "/Qm64"),
                           ])
    def test_arch_flag_intel(self, os_, arch, flag):
        settings = MockSettings({"compiler": "intel-cc",
                                 "os": os_,
                                 "arch": arch})
        self.assertEqual(architecture_flag(settings), flag)

    @parameterized.expand([("e2k-v2", "-march=elbrus-v2"),
                           ("e2k-v3", "-march=elbrus-v3"),
                           ("e2k-v4", "-march=elbrus-v4"),
                           ("e2k-v5", "-march=elbrus-v5"),
                           ("e2k-v6", "-march=elbrus-v6"),
                           ("e2k-v7", "-march=elbrus-v7"),
                           ])
    def test_arch_flag_mcst_lcc(self, arch, flag):
        settings = MockSettings({"compiler": "mcst-lcc",
                                 "arch": arch})
        self.assertEqual(architecture_flag(settings), flag)

    @parameterized.expand([("msvc", "Debug", None, "-Zi -Ob0 -Od"),
                           ("msvc", "Release", None, "-O2 -Ob2"),
                           ("msvc", "RelWithDebInfo", None, "-Zi -O2 -Ob1"),
                           ("msvc", "MinSizeRel", None, "-O1 -Ob1"),
                           ("msvc", "Debug", "v140_clang_c2", "-gline-tables-only -fno-inline -O0"),
                           ("msvc", "Release", "v140_clang_c2", "-O2"),
                           ("msvc", "RelWithDebInfo", "v140_clang_c2", "-gline-tables-only -O2 -fno-inline"),
                           ("msvc", "MinSizeRel", "v140_clang_c2", ""),
                           ("gcc", "Debug", None, "-g"),
                           ("gcc", "Release", None, "-O3"),
                           ("gcc", "RelWithDebInfo", None, "-O2 -g"),
                           ("gcc", "MinSizeRel", None, "-Os"),
                           ("clang", "Debug", None, "-g"),
                           ("clang", "Release", None, "-O3"),
                           ("clang", "RelWithDebInfo", None, "-O2 -g"),
                           ("clang", "MinSizeRel", None, "-Os"),
                           ("apple-clang", "Debug", None, "-g"),
                           ("apple-clang", "Release", None, "-O3"),
                           ("apple-clang", "RelWithDebInfo", None, "-O2 -g"),
                           ("apple-clang", "MinSizeRel", None, "-Os"),
                           ("sun-cc", "Debug", None, "-g"),
                           ("sun-cc", "Release", None, "-xO3"),
                           ("sun-cc", "RelWithDebInfo", None, "-xO2 -g"),
                           ("sun-cc", "MinSizeRel", None, "-xO2 -xspace"),
                           ])
    def test_build_type_flags(self, compiler, build_type, vs_toolset, flags):
        settings = MockSettings({"compiler": compiler,
                                 "build_type": build_type,
                                 "compiler.toolset": vs_toolset})
        self.assertEqual(' '.join(build_type_flags(settings)),
                         flags)
