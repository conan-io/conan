#!/usr/bin/env python
# -*- coding: utf-8 -*-

import platform
import unittest
from nose.plugins.attrib import attr
from conans.model.settings import Settings
from conans.client.conf import default_settings_yml
from conans.errors import ConanException
from conans.client import tools
from conans.client.tools.env import environment_append


@attr('visual_studio')
@unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
class VCVarsArchTest(unittest.TestCase):

    def assert_vcvars_command(self, settings, expected, **kwargs):
        command = tools.vcvars_command(settings, **kwargs)
        command = command.replace('"', '').replace("'", "")
        self.assertTrue(command.endswith('vcvarsall.bat %s' % expected))

    def test_arch(self):
        settings = Settings.loads(default_settings_yml)
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '14'

        settings.arch = 'x86'
        self.assert_vcvars_command(settings, "x86")
        with environment_append({"PreferredToolArchitecture": "x64"}):
            self.assert_vcvars_command(settings, "amd64_x86")

        settings.arch = 'x86_64'
        self.assert_vcvars_command(settings, "amd64")

        settings.arch = 'armv7'
        self.assert_vcvars_command(settings, "amd64_arm")

        settings.arch = 'armv8'
        self.assert_vcvars_command(settings, "amd64_arm64")

        settings.arch = 'mips'
        with self.assertRaises(ConanException):
            tools.vcvars_command(settings)

        settings.arch_build = 'x86_64'
        settings.arch = 'x86'
        self.assert_vcvars_command(settings, "amd64_x86")

    def test_arch_override(self):
        settings = Settings.loads(default_settings_yml)
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '14'
        settings.arch = 'mips64'

        self.assert_vcvars_command(settings, "x86", arch='x86')
        self.assert_vcvars_command(settings, "amd64", arch='x86_64')
        self.assert_vcvars_command(settings, "amd64_arm", arch='armv7')
        self.assert_vcvars_command(settings, "amd64_arm64", arch='armv8')

        with self.assertRaises(ConanException):
            tools.vcvars_command(settings, arch='mips')

    def test_vcvars_ver_override(self):
        settings = Settings.loads(default_settings_yml)
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '15'
        settings.arch = 'x86_64'

        command = tools.vcvars_command(settings, vcvars_ver='14.14')
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('-vcvars_ver=14.14', command)

        settings.compiler.version = '14'

        command = tools.vcvars_command(settings, vcvars_ver='14.14')
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('-vcvars_ver=14.14', command)

    def test_winsdk_version_override(self):
        settings = Settings.loads(default_settings_yml)
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '15'
        settings.arch = 'x86_64'

        command = tools.vcvars_command(settings, winsdk_version='8.1')
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('8.1', command)

        settings.compiler.version = '14'

        command = tools.vcvars_command(settings, winsdk_version='8.1')
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('8.1', command)
