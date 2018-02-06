#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import platform
from nose.plugins.attrib import attr

from conans.client.build.compiler_flags import architecture_flags, libcxx_flags, pic_flags, CompilerFlags, \
    adjust_path, sysroot_flags, format_defines, format_include_paths, format_library_paths, format_libraries, \
    build_type_flags


class CompilerFlagsTest(unittest.TestCase):
    def test_merge(self):
        flags1 = CompilerFlags(cflags=['--foo'], cxxflags=['--bar'])
        flags2 = CompilerFlags(cflags=['--fizz'], ldflags=['--buzz'])
        flags1.append(additional_flags=flags2)
        self.assertEquals(flags1.cflags, ['--foo', '--fizz'])
        self.assertEquals(flags1.cxxflags, ['--bar'])
        self.assertEquals(flags1.ldflags, ['--buzz'])
        self.assertEquals(flags1.defines, [])

    def test_arch_flags(self):
        arch_flags = architecture_flags(arch='x86', compiler='gcc')
        self.assertEquals(arch_flags.cflags, ['-m32'])
        self.assertEquals(arch_flags.cxxflags, ['-m32'])
        self.assertEquals(arch_flags.ldflags, ['-m32'])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = architecture_flags(arch='x86', compiler='clang')
        self.assertEquals(arch_flags.cflags, ['-m32'])
        self.assertEquals(arch_flags.cxxflags, ['-m32'])
        self.assertEquals(arch_flags.ldflags, ['-m32'])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = architecture_flags(arch='sparc', compiler='sun-cc')
        self.assertEquals(arch_flags.cflags, ['-m32'])
        self.assertEquals(arch_flags.cxxflags, ['-m32'])
        self.assertEquals(arch_flags.ldflags, ['-m32'])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = architecture_flags(arch='x86_64', compiler='gcc')
        self.assertEquals(arch_flags.cflags, ['-m64'])
        self.assertEquals(arch_flags.cxxflags, ['-m64'])
        self.assertEquals(arch_flags.ldflags, ['-m64'])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = architecture_flags(arch='x86_64', compiler='clang')
        self.assertEquals(arch_flags.cflags, ['-m64'])
        self.assertEquals(arch_flags.cxxflags, ['-m64'])
        self.assertEquals(arch_flags.ldflags, ['-m64'])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = architecture_flags(arch='sparcv9', compiler='sun-cc')
        self.assertEquals(arch_flags.cflags, ['-m64'])
        self.assertEquals(arch_flags.cxxflags, ['-m64'])
        self.assertEquals(arch_flags.ldflags, ['-m64'])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = architecture_flags(arch='armv7', compiler='gcc')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, [])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = architecture_flags(arch='x86', compiler='Visual Studio')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, [])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

    def test_libcxx_flags(self):
        arch_flags = libcxx_flags(compiler='gcc', libcxx='libstdc++')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, [])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, ['_GLIBCXX_USE_CXX11_ABI=0'])

        arch_flags = libcxx_flags(compiler='gcc', libcxx='libstdc++11')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, [])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, ['_GLIBCXX_USE_CXX11_ABI=1'])

        arch_flags = libcxx_flags(compiler='clang', libcxx='libc++')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-stdlib=libc++'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = libcxx_flags(compiler='clang', libcxx='libstdc++')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-stdlib=libstdc++'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, ['_GLIBCXX_USE_CXX11_ABI=0'])

        arch_flags = libcxx_flags(compiler='clang', libcxx='libstdc++11')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-stdlib=libstdc++'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, ['_GLIBCXX_USE_CXX11_ABI=1'])

        arch_flags = libcxx_flags(compiler='apple-clang', libcxx='libc++')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-stdlib=libc++'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = libcxx_flags(compiler='Visual Studio')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, [])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = libcxx_flags(compiler='sun-cc', libcxx='libCstd')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-library=Cstd'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = libcxx_flags(compiler='sun-cc', libcxx='libstdcxx')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-library=stdcxx4'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = libcxx_flags(compiler='sun-cc', libcxx='libstlport')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-library=stlport4'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = libcxx_flags(compiler='sun-cc', libcxx='libstdc++')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-library=stdcpp'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

    def test_pic_flags(self):
        flags = pic_flags()
        self.assertEquals(flags.cflags, ['-fPIC'])
        self.assertEquals(flags.cxxflags, ['-fPIC'])
        self.assertEquals(flags.ldflags, [])
        self.assertEquals(flags.defines, [])

        flags = pic_flags(compiler='gcc')
        self.assertEquals(flags.cflags, ['-fPIC'])
        self.assertEquals(flags.cxxflags, ['-fPIC'])
        self.assertEquals(flags.ldflags, [])
        self.assertEquals(flags.defines, [])

        flags = pic_flags(compiler='Visual Studio')
        self.assertEquals(flags.cflags, [])
        self.assertEquals(flags.cxxflags, [])
        self.assertEquals(flags.ldflags, [])
        self.assertEquals(flags.defines, [])

    def test_build_type_flags(self):
        flags = build_type_flags(compiler='Visual Studio', build_type='Debug')
        self.assertEquals(flags.cflags, ['/Zi'])
        self.assertEquals(flags.cxxflags, ['/Zi'])
        self.assertEquals(flags.ldflags, [])
        self.assertEquals(flags.defines, [])

        flags = build_type_flags(compiler='Visual Studio', build_type='Release')
        self.assertEquals(flags.cflags, [])
        self.assertEquals(flags.cxxflags, [])
        self.assertEquals(flags.ldflags, [])
        self.assertEquals(flags.defines, [])

        flags = build_type_flags(compiler='gcc', build_type='Debug')
        self.assertEquals(flags.cflags, ['-g'])
        self.assertEquals(flags.cxxflags, ['-g'])
        self.assertEquals(flags.ldflags, [])
        self.assertEquals(flags.defines, [])

        flags = build_type_flags(compiler='gcc', build_type='Release')
        self.assertEquals(flags.cflags, ['-s'])
        self.assertEquals(flags.cxxflags, ['-s'])
        self.assertEquals(flags.ldflags, [])
        self.assertEquals(flags.defines, ['NDEBUG'])

        flags = build_type_flags(compiler='clang', build_type='Debug')
        self.assertEquals(flags.cflags, ['-g'])
        self.assertEquals(flags.cxxflags, ['-g'])
        self.assertEquals(flags.ldflags, [])
        self.assertEquals(flags.defines, [])

        flags = build_type_flags(compiler='clang', build_type='Release')
        self.assertEquals(flags.cflags, [])
        self.assertEquals(flags.cxxflags, [])
        self.assertEquals(flags.cxxflags, [])
        self.assertEquals(flags.ldflags, [])
        self.assertEquals(flags.defines, [])

    def test_adjust_path(self):
        self.assertEquals('home/www', adjust_path('home\\www'))
        self.assertEquals('home/www', adjust_path('home\\www', compiler='gcc'))

        self.assertEquals('"home/www root"', adjust_path('home\\www root'))
        self.assertEquals('"home/www root"', adjust_path('home\\www root', compiler='gcc'))

    @attr('visual_studio')
    def test_adjust_path_visual_studio(self):
        # NOTE : test cannot be run on *nix systems, as adjust_path uses tools.unix_path which is Windows-only
        if platform.system() != "Windows":
            return
        self.assertEquals('home\\www', adjust_path('home/www', compiler='Visual Studio'))
        self.assertEquals('"home\\www root"', adjust_path('home/www root', compiler='Visual Studio'))
        self.assertEquals('home/www', adjust_path('home\\www', compiler='Visual Studio', win_bash=True))
        self.assertEquals('home/www', adjust_path('home/www', compiler='Visual Studio', win_bash=True))
        self.assertEquals('"home/www root"', adjust_path('home\\www root', compiler='Visual Studio', win_bash=True))
        self.assertEquals('"home/www root"', adjust_path('home/www root', compiler='Visual Studio', win_bash=True))

    def test_sysroot_flag(self):
        sysroot = sysroot_flags(sysroot=None)
        self.assertEquals(sysroot.cflags, [])
        self.assertEquals(sysroot.cxxflags, [])
        self.assertEquals(sysroot.ldflags, [])
        self.assertEquals(sysroot.defines, [])
        sysroot = sysroot_flags(sysroot='sys/root', compiler='Visual Studio')
        self.assertEquals(sysroot.cflags, [])
        self.assertEquals(sysroot.cxxflags, [])
        self.assertEquals(sysroot.ldflags, [])
        self.assertEquals(sysroot.defines, [])
        sysroot = sysroot_flags(sysroot='sys/root')
        self.assertEquals(sysroot.cflags, ['--sysroot=sys/root'])
        self.assertEquals(sysroot.cxxflags, ['--sysroot=sys/root'])
        self.assertEquals(sysroot.ldflags, ['--sysroot=sys/root'])
        self.assertEquals(sysroot.defines, [])

    def test_format_defines(self):
        self.assertEquals(['-DFOO', '-DBAR=1'], format_defines(['FOO', 'BAR=1']))

    def test_format_include_paths(self):
        self.assertEquals(['-Ipath1', '-I"with spaces"'], format_include_paths(['path1', 'with spaces']))

    def test_format_library_paths(self):
        self.assertEquals(['-Lpath1', '-L"with spaces"'], format_library_paths(['path1', 'with spaces']))
        self.assertEquals(['-LIBPATH:path1', '-LIBPATH:"with spaces"'],
                          format_library_paths(['path1', 'with spaces'], compiler='Visual Studio'))

    def test_format_libraries(self):
        self.assertEquals(['-llib1', '-llib2'], format_libraries(['lib1', 'lib2']))
        self.assertEquals(['lib1', 'lib2'], format_libraries(['lib1', 'lib2'], compiler='Visual Studio'))
