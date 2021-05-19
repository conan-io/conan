#!/usr/bin/env python
# -*- coding: utf-8 -*-

import platform
import unittest

import pytest

from conans.client import tools
from conans.client.conf import get_default_settings_yml
from conans.client.tools.env import environment_append
from conans.errors import ConanException
from conans.model.settings import Settings
from conans.test.utils.mocks import TestBufferConanOutput


@pytest.mark.tool_visual_studio
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
class VCVarsArchTest(unittest.TestCase):
    output = TestBufferConanOutput()

    def assert_vcvars_command(self, settings, expected, output=None, **kwargs):
        output = output or self.output
        command = tools.vcvars_command(settings, output=output, **kwargs)
        command = command.replace('"', '').replace("'", "")
        self.assertTrue(command.endswith('vcvarsall.bat %s' % expected),
                        msg="'{}' doesn't end with 'vcvarsall.bat {}'".format(command, expected))

    def test_arch(self):
        settings = Settings.loads(get_default_settings_yml())
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
            tools.vcvars_command(settings, output=self.output)

        settings.arch_build = 'x86_64'
        settings.arch = 'x86'
        self.assert_vcvars_command(settings, "amd64_x86")

    def test_arch_override(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '14'
        settings.arch = 'mips64'

        self.assert_vcvars_command(settings, "x86", arch='x86')
        self.assert_vcvars_command(settings, "amd64", arch='x86_64')
        self.assert_vcvars_command(settings, "amd64_arm", arch='armv7')
        self.assert_vcvars_command(settings, "amd64_arm64", arch='armv8')

        with self.assertRaises(ConanException):
            tools.vcvars_command(settings, arch='mips', output=self.output)

    def test_vcvars_ver_override(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '15'
        settings.arch = 'x86_64'

        command = tools.vcvars_command(settings, vcvars_ver='14.14', output=self.output)
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('-vcvars_ver=14.14', command)

        settings.compiler.version = '14'

        command = tools.vcvars_command(settings, vcvars_ver='14.14', output=self.output)
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('-vcvars_ver=14.14', command)

    def test_winsdk_version_override(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '15'
        settings.arch = 'x86_64'

        command = tools.vcvars_command(settings, winsdk_version='8.1', output=self.output)
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('8.1', command)

        settings.compiler.version = '14'

        command = tools.vcvars_command(settings, winsdk_version='8.1', output=self.output)
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('8.1', command)

    def test_windows_ce(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = 'WindowsCE'
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '15'
        settings.arch = 'armv4i'
        self.assert_vcvars_command(settings, "x86")
