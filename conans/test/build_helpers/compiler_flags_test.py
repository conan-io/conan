#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import platform
from nose.plugins.attrib import attr

from conans.client.build.compiler_flags import architecture_flag, libcxx_flag, libcxx_define, \
    pic_flag, build_type_flag, build_type_define, adjust_path, sysroot_flag, format_defines, \
    format_include_paths, format_library_paths, format_libraries


class CompilerFlagsTest(unittest.TestCase):

    def test_arch_flag(self):
        for compiler in ("gcc", "clang", "sun-cc"):
            arch_flag = architecture_flag(arch='x86', compiler=compiler)
            self.assertEquals(arch_flag, '-m32')

        arch_flag = architecture_flag(arch='sparc', compiler='sun-cc')
        self.assertEquals(arch_flag, '-m32')

        for compiler in ("gcc", "clang", "sun-cc"):
            arch_flag = architecture_flag(arch='x86_64', compiler=compiler)
            self.assertEquals(arch_flag, '-m64')

        arch_flag = architecture_flag(arch='sparcv9', compiler='sun-cc')
        self.assertEquals(arch_flag, '-m64')

        for compiler in ("gcc", "clang", "sun-cc"):
            arch_flag = architecture_flag(arch='armv7', compiler=compiler)
            self.assertEquals(arch_flag, '')

        arch_flag = architecture_flag(arch='x86', compiler='Visual Studio')
        self.assertEquals(arch_flag, '')

        arch_flag = architecture_flag(arch='x86_64', compiler='Visual Studio')
        self.assertEquals(arch_flag, '')

    def test_libcxx_flags(self):
        arch_define = libcxx_define(compiler='gcc', libcxx='libstdc++')
        self.assertEquals(arch_define, '_GLIBCXX_USE_CXX11_ABI=0')

        arch_define = libcxx_define(compiler='gcc', libcxx='libstdc++11')
        self.assertEquals(arch_define, '_GLIBCXX_USE_CXX11_ABI=1')

        arch_flags = libcxx_flag(compiler='clang', libcxx='libc++')
        self.assertEquals(arch_flags, '-stdlib=libc++')

        arch_flags = libcxx_flag(compiler='clang', libcxx='libstdc++')
        self.assertEquals(arch_flags, '-stdlib=libstdc++')

        arch_define = libcxx_define(compiler='clang', libcxx='libstdc++')
        self.assertEquals(arch_define, '_GLIBCXX_USE_CXX11_ABI=0')

        arch_flags = libcxx_flag(compiler='clang', libcxx='libstdc++')
        self.assertEquals(arch_flags, '-stdlib=libstdc++')
        arch_define = libcxx_define(compiler='clang', libcxx='libstdc++')
        self.assertEquals(arch_define, '_GLIBCXX_USE_CXX11_ABI=0')

        arch_flags = libcxx_flag(compiler='apple-clang', libcxx='libc++')
        self.assertEquals(arch_flags, '-stdlib=libc++')

        arch_flags = libcxx_flag(compiler='Visual Studio', libcxx=None)
        self.assertEquals(arch_flags, "")

        arch_flags = libcxx_flag(compiler='sun-cc', libcxx='libCstd')
        self.assertEquals(arch_flags, '-library=Cstd')

        arch_flags = libcxx_flag(compiler='sun-cc', libcxx='libstdcxx')
        self.assertEquals(arch_flags, '-library=stdcxx4')

        arch_flags = libcxx_flag(compiler='sun-cc', libcxx='libstlport')
        self.assertEquals(arch_flags, '-library=stlport4')

        arch_flags = libcxx_flag(compiler='sun-cc', libcxx='libstdc++')
        self.assertEquals(arch_flags, '-library=stdcpp')

    def test_pic_flags(self):
        flag = pic_flag()
        self.assertEquals(flag, '')

        flags = pic_flag(compiler='gcc')
        self.assertEquals(flags, '-fPIC')

        flags = pic_flag(compiler='Visual Studio')
        self.assertEquals(flags, "")

    def test_build_type_flags(self):
        flags = build_type_flag(compiler='Visual Studio', build_type='Debug')
        self.assertEquals(flags, '-Zi')

        flags = build_type_flag(compiler='Visual Studio', build_type='Release')
        self.assertEquals(flags, "")

        flags = build_type_flag(compiler='gcc', build_type='Debug')
        self.assertEquals(flags, '-g')

        flags = build_type_flag(compiler='gcc', build_type='Release')
        self.assertEquals(flags, '-s')
        define = build_type_define(build_type='Release')
        self.assertEquals(define, 'NDEBUG')

        flags = build_type_flag(compiler='clang', build_type='Debug')
        self.assertEquals(flags, '-g')

        flags = build_type_flag(compiler='clang', build_type='Release')
        self.assertEquals(flags, '')

    def test_adjust_path(self):
        self.assertEquals('home/www', adjust_path('home\\www'))
        self.assertEquals('home/www', adjust_path('home\\www', compiler='gcc'))

        self.assertEquals('"home/www root"', adjust_path('home\\www root'))
        self.assertEquals('"home/www root"', adjust_path('home\\www root', compiler='gcc'))

    @attr('visual_studio')
    def test_adjust_path_visual_studio(self):
        #  NOTE : test cannot be run on *nix systems, as adjust_path uses
        # tools.unix_path which is Windows-only
        if platform.system() != "Windows":
            return
        self.assertEquals('home\\www', adjust_path('home/www', compiler='Visual Studio'))
        self.assertEquals('"home\\www root"',
                          adjust_path('home/www root', compiler='Visual Studio'))
        self.assertEquals('home/www',
                          adjust_path('home\\www', compiler='Visual Studio', win_bash=True))
        self.assertEquals('home/www',
                          adjust_path('home/www', compiler='Visual Studio', win_bash=True))
        self.assertEquals('"home/www root"',
                          adjust_path('home\\www root', compiler='Visual Studio', win_bash=True))
        self.assertEquals('"home/www root"',
                          adjust_path('home/www root', compiler='Visual Studio', win_bash=True))

    def test_sysroot_flag(self):
        sysroot = sysroot_flag(sysroot=None)
        self.assertEquals(sysroot, "")

        sysroot = sysroot_flag(sysroot='sys/root', compiler='Visual Studio')
        self.assertEquals(sysroot, "")

        sysroot = sysroot_flag(sysroot='sys/root')
        self.assertEquals(sysroot, "--sysroot=sys/root")

    def test_format_defines(self):
        self.assertEquals(['-DFOO', '-DBAR=1'], format_defines(['FOO', 'BAR=1'], "gcc"))

    def test_format_include_paths(self):
        self.assertEquals(['-Ipath1', '-I"with spaces"'], format_include_paths(['path1', 'with spaces']))

    def test_format_library_paths(self):
        self.assertEquals(['-Lpath1', '-L"with spaces"'], format_library_paths(['path1', 'with spaces']))
        self.assertEquals(['-LIBPATH:path1', '-LIBPATH:"with spaces"'],
                          format_library_paths(['path1', 'with spaces'], compiler='Visual Studio'))

    def test_format_libraries(self):
        self.assertEquals(['-llib1', '-llib2'], format_libraries(['lib1', 'lib2']))
        self.assertEquals(['lib1.lib', 'lib2.lib'], format_libraries(['lib1', 'lib2'],
                                                                     compiler='Visual Studio'))
