#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4


import unittest
from conans import tools
from conans.test.util.tools_test import RunnerMock
from conans.test.utils.conanfile import MockSettings


class CompilerIdTest(unittest.TestCase):
    def test_unknown(self):
        runner = RunnerMock()
        runner.output = "#define UNKNOWN 1"

        compiler_id = tools.compiler_id('gcc', runner=runner)
        self.assertEqual(compiler_id, tools.UNKWNON_COMPILER)

    def test_malformed_numbers(self):
        runner = RunnerMock()
        runner.output = "#define __GNUC__ A\n" \
                        "#define __GNUC_MINOR__ B\n" \
                        "#define __GNUC_PATCHLEVEL__ C\n"

        compiler_id = tools.compiler_id('gcc', runner=runner)
        self.assertEqual(compiler_id, tools.UNKWNON_COMPILER)

    def test_incomplete(self):
        runner = RunnerMock()
        runner.output = "#define __GNUC__ 1\n"

        compiler_id = tools.compiler_id('gcc', runner=runner)
        self.assertEqual(compiler_id, tools.UNKWNON_COMPILER)

    def test_gcc(self):
        runner = RunnerMock()
        runner.output = "#define __GNUC__ 7\n" \
                        "#define __GNUC_MINOR__ 3\n" \
                        "#define __GNUC_PATCHLEVEL__ 0\n"

        compiler_id = tools.compiler_id('gcc', runner=runner)
        self.assertEqual(compiler_id, tools.CompilerId(tools.GCC, 7, 3, 0))

    def test_clang(self):
        runner = RunnerMock()
        runner.output = "#define __clang_major__ 6\n" \
                        "#define __clang_minor__ 0\n" \
                        "#define __clang_patchlevel__ 0\n"

        compiler_id = tools.compiler_id('clang', runner=runner)
        self.assertEqual(compiler_id, tools.CompilerId(tools.CLANG, 6, 0, 0))

    def test_apple_clang(self):
        runner = RunnerMock()
        runner.output = "#define __apple_build_version__ 6000057\n" \
                        "#define __clang_major__ 9\n" \
                        "#define __clang_minor__ 1\n" \
                        "#define __clang_patchlevel__ 0\n"

        compiler_id = tools.compiler_id('clang', runner=runner)
        self.assertEqual(compiler_id, tools.CompilerId(tools.APPLE_CLANG, 9, 1, 0))


    def test_real(self):
        print(tools.compiler_id('gcc'))
        print(tools.compiler_id('g++'))
        print(tools.compiler_id('clang'))
        print(tools.compiler_id('clang++'))

        fake_settings = MockSettings({'compiler': 'gcc'})
        print(tools.guess_c_compiler(fake_settings))
        print(tools.guess_cxx_compiler(fake_settings))

        fake_settings = MockSettings({'compiler': 'clang'})
        print(tools.guess_c_compiler(fake_settings))
        print(tools.guess_cxx_compiler(fake_settings))
