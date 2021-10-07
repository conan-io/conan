#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import unittest
import warnings

from six import StringIO

from conans.client import tools
from conans.client.output import ConanOutput
from conans.client.tools.oss import cpu_count
from conans.client.tools.win import build_sln_command
from conans.errors import ConanException
from conans.model.settings import Settings
from conans.test.utils.mocks import MockSettings
from conans.test.utils.test_files import temp_folder
from conans.util.files import load, save


class BuildSLNCommandTest(unittest.TestCase):

    def test_no_configuration(self):
        dummy = """GlobalSection
            EndGlobalSection
     GlobalSection(SolutionConfigurationPlatforms) = preSolution
        Debug|Win32 = Debug|Win32
        Debug|x64 = Debug|x64
        Release|Win32 = Release|Win32
        Release|x64 = Release|x64
    EndGlobalSection
"""
        folder = temp_folder()
        path = os.path.join(folder, "dummy.sln")
        save(path, dummy)

        new_out = StringIO()
        command = build_sln_command(Settings({}), sln_path=path, targets=None, upgrade_project=False,
                                    build_type='Debug', arch="x86", parallel=False,
                                    output=ConanOutput(new_out))

        self.assertIn('/p:Configuration="Debug" /p:UseEnv=false /p:Platform="x86"', command)
        self.assertIn("WARN: ***** The configuration Debug|x86 does not exist in this solution *****",
                      new_out.getvalue())

        # use platforms
        new_out = StringIO()
        command = build_sln_command(Settings({}), sln_path=path, targets=None, upgrade_project=False,
                                    build_type='Debug', arch="x86", parallel=False,
                                    platforms={"x86": "Win32"}, output=ConanOutput(new_out))

        self.assertIn('/p:Configuration="Debug" /p:UseEnv=false /p:Platform="Win32"', command)
        self.assertNotIn("WARN", new_out.getvalue())
        self.assertNotIn("ERROR", new_out.getvalue())

    def test_no_arch(self):
        with self.assertRaises(ConanException):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")

                new_out = StringIO()
                build_sln_command(Settings({}), sln_path='dummy.sln', targets=None,
                                  upgrade_project=False, build_type='Debug', arch=None, parallel=False,
                                  output=ConanOutput(new_out))

                self.assertEqual(len(w), 1)
                self.assertTrue(issubclass(w[0].category, DeprecationWarning))

    def test_no_build_type(self):
        with self.assertRaises(ConanException):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")

                new_out = StringIO()
                build_sln_command(Settings({}), sln_path='dummy.sln', targets=None,
                                  upgrade_project=False, build_type=None, arch='x86', parallel=False,
                                  output=ConanOutput(new_out))

                self.assertEqual(len(w), 1)
                self.assertTrue(issubclass(w[0].category, DeprecationWarning))

    def test_positive(self):
        output = ConanOutput(StringIO())
        command = build_sln_command(Settings({}), sln_path='dummy.sln', targets=None,
                                    upgrade_project=False, build_type='Debug', arch='x86',
                                    parallel=False, output=output)

        self.assertIn('msbuild "dummy.sln"', command)
        self.assertIn('/p:Platform="x86"', command)
        self.assertNotIn('devenv "dummy.sln" /upgrade', command)
        self.assertNotIn('/m:%s' % cpu_count(output=output), command)
        self.assertNotIn('/target:teapot', command)

    def test_upgrade(self):
        output = ConanOutput(StringIO())
        command = build_sln_command(Settings({}), sln_path='dummy.sln', targets=None,
                                    upgrade_project=True, build_type='Debug', arch='x86_64',
                                    parallel=False, output=output)

        self.assertIn('msbuild "dummy.sln"', command)
        self.assertIn('/p:Platform="x64"', command)
        self.assertIn('devenv "dummy.sln" /upgrade', command)
        self.assertNotIn('/m:%s' % cpu_count(output=output), command)
        self.assertNotIn('/target:teapot', command)

        with tools.environment_append({"CONAN_SKIP_VS_PROJECTS_UPGRADE": "1"}):
            output = ConanOutput(StringIO())
            command = build_sln_command(Settings({}), sln_path='dummy.sln', targets=None,
                                        upgrade_project=True, build_type='Debug', arch='x86_64',
                                        parallel=False, output=output)

            self.assertIn('msbuild "dummy.sln"', command)
            self.assertIn('/p:Platform="x64"', command)
            self.assertNotIn('devenv "dummy.sln" /upgrade', command)
            self.assertNotIn('/m:%s' % cpu_count(output=output), command)
            self.assertNotIn('/target:teapot', command)

        with tools.environment_append({"CONAN_SKIP_VS_PROJECTS_UPGRADE": "False"}):
            output = ConanOutput(StringIO())
            command = build_sln_command(Settings({}), sln_path='dummy.sln', targets=None,
                                        upgrade_project=True, build_type='Debug', arch='x86_64',
                                        parallel=False, output=output)

            self.assertIn('devenv "dummy.sln" /upgrade', command)

    def test_parallel(self):
        output = ConanOutput(StringIO())
        command = build_sln_command(Settings({}), sln_path='dummy.sln', targets=None,
                                    upgrade_project=True, build_type='Debug', arch='armv7',
                                    parallel=False, output=output)

        self.assertIn('msbuild "dummy.sln"', command)
        self.assertIn('/p:Platform="ARM"', command)
        self.assertIn('devenv "dummy.sln" /upgrade', command)
        self.assertNotIn('/m:%s' % cpu_count(output=output), command)
        self.assertNotIn('/target:teapot', command)

    def test_target(self):
        output = ConanOutput(StringIO())
        command = build_sln_command(Settings({}), sln_path='dummy.sln', targets=['teapot'],
                                    upgrade_project=False, build_type='Debug', arch='armv8',
                                    parallel=False, output=output)

        self.assertIn('msbuild "dummy.sln"', command)
        self.assertIn('/p:Platform="ARM64"', command)
        self.assertNotIn('devenv "dummy.sln" /upgrade', command)
        self.assertNotIn('/m:%s' % cpu_count(output=output), command)
        self.assertIn('/target:teapot', command)

    def test_toolset(self):
        new_out = StringIO()
        command = build_sln_command(MockSettings({"compiler": "Visual Studio",
                                                  "compiler.version": "17",
                                                  "build_type": "Debug",
                                                  "compiler.runtime": "MDd",
                                                  "cppstd": "17"}),
                                    sln_path='dummy.sln', targets=None,
                                    upgrade_project=False, build_type='Debug', arch='armv7',
                                    parallel=False, toolset="v110", output=ConanOutput(new_out))

        self.assertTrue(command.startswith('msbuild "dummy.sln" /p:Configuration="Debug" '
                                           '/p:UseEnv=false '
                                           '/p:Platform="ARM" '
                                           '/p:PlatformToolset="v110" '
                                           '/verbosity:minimal '
                                           '/p:ForceImportBeforeCppTargets='), command)

    def test_properties_file(self):
        new_out = StringIO()
        command = build_sln_command(MockSettings({"compiler": "Visual Studio",
                                                  "compiler.version": "17",
                                                  "build_type": "Debug",
                                                  "compiler.runtime": "MDd",
                                                  "cppstd": "17"}),
                                    sln_path='dummy.sln', targets=None,
                                    upgrade_project=False, build_type='Debug', arch='armv7',
                                    parallel=False, output=ConanOutput(new_out))

        self.assertTrue(command.startswith('msbuild "dummy.sln" /p:Configuration="Debug" '
                                           '/p:UseEnv=false '
                                           '/p:Platform="ARM" '
                                           '/p:PlatformToolset="v143" '
                                           '/verbosity:minimal '
                                           '/p:ForceImportBeforeCppTargets='), command)
        path_tmp = command.split("/p:ForceImportBeforeCppTargets=")[1][1:-1]  # remove quotes
        self.assertTrue(os.path.exists(path_tmp))
        contents = load(path_tmp)
        self.assertIn("<RuntimeLibrary>MultiThreadedDebugDLL</RuntimeLibrary>", contents)
        self.assertIn("<AdditionalOptions>/std:c++17 %(AdditionalOptions)</AdditionalOptions>",
                      contents)
