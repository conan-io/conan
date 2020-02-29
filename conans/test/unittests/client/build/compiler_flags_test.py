#!/usr/bin/env python
# -*- coding: utf-8 -*-

import platform
import unittest
from parameterized.parameterized import parameterized

from conans.client.build.compiler_flags import adjust_path, architecture_flag, build_type_define, \
    build_type_flags, format_defines, format_include_paths, format_libraries, \
    format_library_paths, libcxx_define, libcxx_flag, pic_flag, sysroot_flag


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
                           ("Visual Studio", "x86", None, ""),
                           ("Visual Studio", "x86_64", None, ""),
                           ("gcc", "ppc32", "AIX", "-maix32"),
                           ("gcc", "ppc64", "AIX", "-maix64"),
                           ])
    def test_arch_flag(self, compiler, arch, os, flag):
        self.assertEqual(architecture_flag(compiler=compiler, arch=arch, os=os), flag)

    @parameterized.expand([("gcc", "libstdc++", "_GLIBCXX_USE_CXX11_ABI=0"),
                           ("gcc", "libstdc++11", "_GLIBCXX_USE_CXX11_ABI=1"),
                           ("clang", "libstdc++", "_GLIBCXX_USE_CXX11_ABI=0"),
                           ("clang", "libstdc++11", "_GLIBCXX_USE_CXX11_ABI=1"),
                           ("clang", "libc++", ""),
                           ("Visual Studio", None, ""),
                           ])
    def test_libcxx_define(self, compiler, libcxx, define):
        self.assertEqual(libcxx_define(compiler=compiler, libcxx=libcxx), define)

    @parameterized.expand([("gcc", "libstdc++", ""),
                           ("gcc", "libstdc++11", ""),
                           ("clang", "libstdc++", "-stdlib=libstdc++"),
                           ("clang", "libstdc++11", "-stdlib=libstdc++"),
                           ("clang", "libc++", "-stdlib=libc++"),
                           ("apple-clang", "libstdc++", "-stdlib=libstdc++"),
                           ("apple-clang", "libstdc++11", "-stdlib=libstdc++"),
                           ("apple-clang", "libc++", "-stdlib=libc++"),
                           ("Visual Studio", None, ""),
                           ("sun-cc", "libCstd", "-library=Cstd"),
                           ("sun-cc", "libstdcxx", "-library=stdcxx4"),
                           ("sun-cc", "libstlport", "-library=stlport4"),
                           ("sun-cc", "libstdc++", "-library=stdcpp")
                           ])
    def test_libcxx_flags(self, compiler, libcxx, flag):
        self.assertEqual(libcxx_flag(compiler=compiler, libcxx=libcxx), flag)

    @parameterized.expand([("cxx",),
                           ("gpp",),
                           ("cpp",),
                           ("cpp-ne",),
                           ("acpp",),
                           ("acpp-ne",),
                           ("ecpp",),
                           ("ecpp-ne",)])
    def test_libcxx_flags_qnx(self, libcxx):
        arch_flags = libcxx_flag(compiler='qcc', libcxx=libcxx)
        self.assertEqual(arch_flags, '-Y _%s' % libcxx)

    def test_pic_flags(self):
        flag = pic_flag()
        self.assertEqual(flag, '')

        flags = pic_flag(compiler='gcc')
        self.assertEqual(flags, '-fPIC')

        flags = pic_flag(compiler='Visual Studio')
        self.assertEqual(flags, "")

    @parameterized.expand([("Visual Studio", "Debug", None, "-Zi -Ob0 -Od"),
                           ("Visual Studio", "Release", None, "-O2 -Ob2"),
                           ("Visual Studio", "RelWithDebInfo", None, "-Zi -O2 -Ob1"),
                           ("Visual Studio", "MinSizeRel", None, "-O1 -Ob1"),
                           ("Visual Studio", "Debug", "v140_clang_c2", "-gline-tables-only -fno-inline -O0"),
                           ("Visual Studio", "Release", "v140_clang_c2", "-O2"),
                           ("Visual Studio", "RelWithDebInfo", "v140_clang_c2", "-gline-tables-only -O2 -fno-inline"),
                           ("Visual Studio", "MinSizeRel", "v140_clang_c2", ""),
                           ("gcc", "Debug", None, "-g"),
                           ("gcc", "Release", None, "-O3 -s"),
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
        self.assertEqual(' '.join(build_type_flags(compiler=compiler, build_type=build_type, vs_toolset=vs_toolset)),
                         flags)

    def test_build_type_define(self):
        define = build_type_define(build_type='Release')
        self.assertEqual(define, 'NDEBUG')

    def test_adjust_path(self):
        self.assertEqual('home/www', adjust_path('home\\www'))
        self.assertEqual('home/www', adjust_path('home\\www', compiler='gcc'))

        self.assertEqual('"home/www root"', adjust_path('home\\www root'))
        self.assertEqual('"home/www root"', adjust_path('home\\www root', compiler='gcc'))

    @unittest.skipUnless(platform.system() == "Windows", "requires Windows")
    def test_adjust_path_visual_studio(self):
        #  NOTE : test cannot be run on *nix systems, as adjust_path uses
        # tools.unix_path which is Windows-only
        self.assertEqual('home\\www', adjust_path('home/www', compiler='Visual Studio'))
        self.assertEqual('"home\\www root"',
                          adjust_path('home/www root', compiler='Visual Studio'))
        self.assertEqual('home/www',
                          adjust_path('home\\www', compiler='Visual Studio', win_bash=True))
        self.assertEqual('home/www',
                          adjust_path('home/www', compiler='Visual Studio', win_bash=True))
        self.assertEqual('"home/www root"',
                          adjust_path('home\\www root', compiler='Visual Studio', win_bash=True))
        self.assertEqual('"home/www root"',
                          adjust_path('home/www root', compiler='Visual Studio', win_bash=True))

    def test_sysroot_flag(self):
        sysroot = sysroot_flag(sysroot=None)
        self.assertEqual(sysroot, "")

        sysroot = sysroot_flag(sysroot='sys/root', compiler='Visual Studio')
        self.assertEqual(sysroot, "")

        sysroot = sysroot_flag(sysroot='sys/root')
        self.assertEqual(sysroot, "--sysroot=sys/root")

    def test_format_defines(self):
        self.assertEqual(['-DFOO', '-DBAR=1'], format_defines(['FOO', 'BAR=1']))

    def test_format_include_paths(self):
        self.assertEqual(['-Ipath1', '-I"with spaces"'], format_include_paths(['path1', 'with spaces']))

    def test_format_library_paths(self):
        self.assertEqual(['-Lpath1', '-L"with spaces"'], format_library_paths(['path1', 'with spaces']))
        self.assertEqual(['-LIBPATH:path1', '-LIBPATH:"with spaces"'],
                          format_library_paths(['path1', 'with spaces'], compiler='Visual Studio'))

    def test_format_libraries(self):
        self.assertEqual(['-llib1', '-llib2'], format_libraries(['lib1', 'lib2']))
        self.assertEqual(['lib1.lib', 'lib2.lib'], format_libraries(['lib1', 'lib2'],
                                                                     compiler='Visual Studio'))
