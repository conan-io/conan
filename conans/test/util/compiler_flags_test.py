#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from conans import tools


class CompilerFlagsTest(unittest.TestCase):
    def test_merge(self):
        flags1 = tools.CompilerFlags(cflags=['--foo'], cxxflags=['--bar'])
        flags2 = tools.CompilerFlags(cflags=['--fizz'], ldflags=['--buzz'])
        flags1.append(additional_flags=flags2)
        self.assertEquals(flags1.cflags, ['--foo', '--fizz'])
        self.assertEquals(flags1.cxxflags, ['--bar'])
        self.assertEquals(flags1.ldflags, ['--buzz'])
        self.assertEquals(flags1.defines, [])

    def test_arch_flags(self):
        arch_flags = tools.architecture_flags(arch='x86', compiler='gcc')
        self.assertEquals(arch_flags.cflags, ['-m32'])
        self.assertEquals(arch_flags.cxxflags, ['-m32'])
        self.assertEquals(arch_flags.ldflags, ['-m32'])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = tools.architecture_flags(arch='x86', compiler='clang')
        self.assertEquals(arch_flags.cflags, ['-m32'])
        self.assertEquals(arch_flags.cxxflags, ['-m32'])
        self.assertEquals(arch_flags.ldflags, ['-m32'])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = tools.architecture_flags(arch='sparc', compiler='sun-cc')
        self.assertEquals(arch_flags.cflags, ['-m32'])
        self.assertEquals(arch_flags.cxxflags, ['-m32'])
        self.assertEquals(arch_flags.ldflags, ['-m32'])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = tools.architecture_flags(arch='x86_64', compiler='gcc')
        self.assertEquals(arch_flags.cflags, ['-m64'])
        self.assertEquals(arch_flags.cxxflags, ['-m64'])
        self.assertEquals(arch_flags.ldflags, ['-m64'])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = tools.architecture_flags(arch='x86_64', compiler='clang')
        self.assertEquals(arch_flags.cflags, ['-m64'])
        self.assertEquals(arch_flags.cxxflags, ['-m64'])
        self.assertEquals(arch_flags.ldflags, ['-m64'])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = tools.architecture_flags(arch='sparcv9', compiler='sun-cc')
        self.assertEquals(arch_flags.cflags, ['-m64'])
        self.assertEquals(arch_flags.cxxflags, ['-m64'])
        self.assertEquals(arch_flags.ldflags, ['-m64'])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = tools.architecture_flags(arch='armv7', compiler='gcc')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, [])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = tools.architecture_flags(arch='x86', compiler='Visual Studio')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, [])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

    def test_libcxx_flags(self):
        arch_flags = tools.libcxx_flags(compiler='gcc', libcxx='libstdc++')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, [])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, ['_GLIBCXX_USE_CXX11_ABI=0'])

        arch_flags = tools.libcxx_flags(compiler='gcc', libcxx='libstdc++11')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, [])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, ['_GLIBCXX_USE_CXX11_ABI=1'])

        arch_flags = tools.libcxx_flags(compiler='clang', libcxx='libc++')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-stdlib=libc++'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = tools.libcxx_flags(compiler='clang', libcxx='libstdc++')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-stdlib=libstdc++'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, ['_GLIBCXX_USE_CXX11_ABI=0'])

        arch_flags = tools.libcxx_flags(compiler='clang', libcxx='libstdc++11')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-stdlib=libstdc++'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, ['_GLIBCXX_USE_CXX11_ABI=1'])

        arch_flags = tools.libcxx_flags(compiler='apple-clang', libcxx='libc++')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-stdlib=libc++'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = tools.libcxx_flags(compiler='Visual Studio')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, [])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = tools.libcxx_flags(compiler='sun-cc', libcxx='libCstd')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-library=Cstd'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = tools.libcxx_flags(compiler='sun-cc', libcxx='libstdcxx')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-library=stdcxx4'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = tools.libcxx_flags(compiler='sun-cc', libcxx='libstlport')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-library=stlport4'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])

        arch_flags = tools.libcxx_flags(compiler='sun-cc', libcxx='libstdc++')
        self.assertEquals(arch_flags.cflags, [])
        self.assertEquals(arch_flags.cxxflags, ['-library=stdcpp'])
        self.assertEquals(arch_flags.ldflags, [])
        self.assertEquals(arch_flags.defines, [])
