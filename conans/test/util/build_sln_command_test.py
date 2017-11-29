#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from conans.tools import build_sln_command, cpu_count
from conans.errors import ConanException
from conans.model.settings import Settings
from nose.plugins.attrib import attr


@attr('visual_studio')
class BuildSLNCommandTest(unittest.TestCase):
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
