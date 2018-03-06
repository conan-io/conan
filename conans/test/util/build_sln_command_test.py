#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from conans import tools
from conans.tools import build_sln_command, cpu_count
from conans.errors import ConanException
from conans.model.settings import Settings
from nose.plugins.attrib import attr
from conans.util.files import save
from six import StringIO
from conans.client.output import ConanOutput
from conans.test.utils.test_files import temp_folder
import os


@attr('visual_studio')
class BuildSLNCommandTest(unittest.TestCase):
    def no_configuration_test(self):
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
        tools.set_global_instances(ConanOutput(new_out), None)
        command = build_sln_command(Settings({}), sln_path=path, targets=None, upgrade_project=False,
                                    build_type='Debug', arch="x86", parallel=False)
        self.assertIn('/p:Configuration=Debug /p:Platform="x86"', command)
        self.assertIn("WARN: ***** The configuration Debug|x86 does not exist in this solution *****",
                      new_out.getvalue())
        # use platforms
        new_out = StringIO()
        tools.set_global_instances(ConanOutput(new_out), None)
        command = build_sln_command(Settings({}), sln_path=path, targets=None, upgrade_project=False,
                                    build_type='Debug', arch="x86", parallel=False, platforms={"x86": "Win32"})
        self.assertIn('/p:Configuration=Debug /p:Platform="Win32"', command)
        self.assertNotIn("WARN", new_out.getvalue())
        self.assertNotIn("ERROR", new_out.getvalue())

    def no_arch_test(self):
        with self.assertRaises(ConanException):
            build_sln_command(Settings({}), sln_path='dummy.sln', targets=None, upgrade_project=False,
                              build_type='Debug', arch=None, parallel=False)

    def no_build_type_test(self):
        with self.assertRaises(ConanException):
            build_sln_command(Settings({}), sln_path='dummy.sln', targets=None, upgrade_project=False,
                              build_type=None, arch='x86', parallel=False)

    def positive_test(self):
        command = build_sln_command(Settings({}), sln_path='dummy.sln', targets=None, upgrade_project=False,
                                    build_type='Debug', arch='x86', parallel=False)
        self.assertIn('msbuild dummy.sln', command)
        self.assertIn('/p:Platform="x86"', command)
        self.assertNotIn('devenv dummy.sln /upgrade', command)
        self.assertNotIn('/m:%s' % cpu_count(), command)
        self.assertNotIn('/target:teapot', command)

    def upgrade_test(self):
        command = build_sln_command(Settings({}), sln_path='dummy.sln', targets=None, upgrade_project=True,
                                    build_type='Debug', arch='x86_64', parallel=False)
        self.assertIn('msbuild dummy.sln', command)
        self.assertIn('/p:Platform="x64"', command)
        self.assertIn('devenv dummy.sln /upgrade', command)
        self.assertNotIn('/m:%s' % cpu_count(), command)
        self.assertNotIn('/target:teapot', command)

        with tools.environment_append({"CONAN_SKIP_VS_PROJECTS_UPGRADE": "1"}):
            command = build_sln_command(Settings({}), sln_path='dummy.sln', targets=None,
                                        upgrade_project=True,
                                        build_type='Debug', arch='x86_64', parallel=False)
            self.assertIn('msbuild dummy.sln', command)
            self.assertIn('/p:Platform="x64"', command)
            self.assertNotIn('devenv dummy.sln /upgrade', command)
            self.assertNotIn('/m:%s' % cpu_count(), command)
            self.assertNotIn('/target:teapot', command)

        with tools.environment_append({"CONAN_SKIP_VS_PROJECTS_UPGRADE": "False"}):
            command = build_sln_command(Settings({}), sln_path='dummy.sln', targets=None,
                                        upgrade_project=True,
                                        build_type='Debug', arch='x86_64', parallel=False)
            self.assertIn('devenv dummy.sln /upgrade', command)

    def parallel_test(self):
        command = build_sln_command(Settings({}), sln_path='dummy.sln', targets=None, upgrade_project=True,
                                    build_type='Debug', arch='armv7', parallel=False)
        self.assertIn('msbuild dummy.sln', command)
        self.assertIn('/p:Platform="ARM"', command)
        self.assertIn('devenv dummy.sln /upgrade', command)
        self.assertNotIn('/m:%s' % cpu_count(), command)
        self.assertNotIn('/target:teapot', command)

    def target_test(self):
        command = build_sln_command(Settings({}), sln_path='dummy.sln', targets=['teapot'], upgrade_project=False,
                                    build_type='Debug', arch='armv8', parallel=False)
        self.assertIn('msbuild dummy.sln', command)
        self.assertIn('/p:Platform="ARM64"', command)
        self.assertNotIn('devenv dummy.sln /upgrade', command)
        self.assertNotIn('/m:%s' % cpu_count(), command)
        self.assertIn('/target:teapot', command)

    def toolset_test(self):
        command = build_sln_command(Settings({}), sln_path='dummy.sln', targets=None,
                                    upgrade_project=False, build_type='Debug', arch='armv7',
                                    parallel=False, toolset="v110")
        self.assertEquals('msbuild dummy.sln /p:Configuration=Debug /p:Platform="ARM" '
                          '/p:PlatformToolset=v110', command)
