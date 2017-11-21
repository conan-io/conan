#!/usr/bin/env python
# -*- coding: utf-8 -*-

import platform
import unittest
from nose.plugins.attrib import attr
from conans.model.settings import Settings
from conans.client.conf import default_settings_yml
from conans.errors import ConanException
from conans import tools


@attr('visual_studio')
class VCVarsArchTest(unittest.TestCase):
    def test_arch(self):
        if platform.system() != "Windows":
            return
        settings = Settings.loads(default_settings_yml)
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '14'

        settings.arch = 'x86'
        command = tools.vcvars_command(settings)
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('x86', command)

        settings.arch = 'x86_64'
        command = tools.vcvars_command(settings)
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('amd64', command)

        settings.arch = 'armv7'
        command = tools.vcvars_command(settings)
        self.assertIn('vcvarsall.bat', command)
        self.assertNotIn('arm64', command)
        self.assertIn('arm', command)

        settings.arch = 'armv8'
        command = tools.vcvars_command(settings)
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('arm64', command)

        settings.arch = 'mips'
        with self.assertRaises(ConanException):
            tools.vcvars_command(settings)

    def test_arch_override(self):
        if platform.system() != "Windows":
            return
        settings = Settings.loads(default_settings_yml)
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '14'
        settings.arch = 'mips64'

        command = tools.vcvars_command(settings, arch='x86')
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('x86', command)

        command = tools.vcvars_command(settings, arch='x86_64')
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('amd64', command)

        command = tools.vcvars_command(settings, arch='armv7')
        self.assertIn('vcvarsall.bat', command)
        self.assertNotIn('arm64', command)
        self.assertIn('arm', command)

        command = tools.vcvars_command(settings, arch='armv8')
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('arm64', command)

        with self.assertRaises(ConanException):
            tools.vcvars_command(settings, arch='mips')
