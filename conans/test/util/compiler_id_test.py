#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4


import unittest
from conans import tools
from conans.test.util.tools_test import RunnerMock
from conans.test.utils.conanfile import MockSettings
from mock import mock
from parameterized import parameterized


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

    def test_clang_cl(self):
        def side_effect(*args, **kwargs):
            if ' --driver-mode=g++' in args[0]:
                kwargs['output'].write("#define __clang_major__ 6\n"
                                       "#define __clang_minor__ 0\n"
                                       "#define __clang_patchlevel__ 1\n")
                return 0
            return 1

        runner_mock = mock.MagicMock(side_effect=side_effect)
        compiler_id = tools.compiler_id('clang-cl.exe', runner=runner_mock)
        self.assertEqual(compiler_id, tools.CompilerId(tools.CLANG, 6, 0, 1, tools.MODE_CL))

    @parameterized.expand([('19.15.26726', 15, 8, 0),
                           ('14.00.50727.762', 8, 0, 0),
                           ('15.00.21022.08', 9, 0, 0),
                           ('16.00.40219.01', 10, 0, 0),
                           ('17.00.60610.1', 11, 0, 0),
                           ('18.00.40629', 12, 0, 0),
                           ('19.00.24210', 14, 0, 0)])
    def test_msvc(self, msc_ver, major, minor, patch):
        def side_effect(*args, **kwargs):
            if ' -E -dM -x c' in args[0]:
                return 1
            elif ' /E /c' in args[0]:
                kwargs['output'].write('Microsoft (R) C/C++ Optimizing Compiler Version %s for x64\n'
                                       'Copyright (C) Microsoft Corporation.  All rights reserved.\n'
                                       'main.cpp\n'
                                       '#line 1 "C:\\bincrafters\\main.cpp"\n'
                                       'int main() {}' % msc_ver)
            return 0

        runner_mock = mock.MagicMock(side_effect=side_effect)
        compiler_id = tools.compiler_id('clang-cl.exe', runner=runner_mock)
        self.assertEqual(compiler_id, tools.CompilerId(tools.MSVC, major, minor, patch, tools.MODE_CL))

    def test_check_version_no_compiler(self):
        compiler_id = tools.CompilerId('gcc', 4, 8, 1)

        fake_settings = MockSettings({})
        self.assertFalse(compiler_id.check_settings(fake_settings))

        fake_settings = MockSettings({'compiler': 'gcc'})
        self.assertFalse(compiler_id.check_settings(fake_settings))

    def test_check_version(self):
        compiler_id = tools.CompilerId('gcc', 4, 8, 1)

        fake_settings = MockSettings({'compiler': 'gcc', 'compiler.version': '4.8.1'})
        self.assertTrue(compiler_id.check_settings(fake_settings))

        fake_settings = MockSettings({'compiler': 'gcc', 'compiler.version': '4.8'})
        self.assertTrue(compiler_id.check_settings(fake_settings))

        fake_settings = MockSettings({'compiler': 'gcc', 'compiler.version': '4'})
        self.assertTrue(compiler_id.check_settings(fake_settings))

    def test_check_version_negative(self):
        compiler_id = tools.CompilerId('gcc', 4, 8, 1)

        fake_settings = MockSettings({'compiler': 'clang', 'compiler.version': '6.0.1'})
        self.assertFalse(compiler_id.check_settings(fake_settings))

        fake_settings = MockSettings({'compiler': 'gcc', 'compiler.version': '8.1.0'})
        self.assertFalse(compiler_id.check_settings(fake_settings))

        fake_settings = MockSettings({'compiler': 'gcc', 'compiler.version': '8.1'})
        self.assertFalse(compiler_id.check_settings(fake_settings))

        fake_settings = MockSettings({'compiler': 'gcc', 'compiler.version': '8'})
        self.assertFalse(compiler_id.check_settings(fake_settings))

        fake_settings = MockSettings({'compiler': 'gcc', 'compiler.version': '4.8.2'})
        self.assertFalse(compiler_id.check_settings(fake_settings))

        fake_settings = MockSettings({'compiler': 'gcc', 'compiler.version': '4.9'})
        self.assertFalse(compiler_id.check_settings(fake_settings))

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
