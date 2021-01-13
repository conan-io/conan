#!/usr/bin/env python
# -*- coding: utf-8 -*-

import platform
import unittest

import pytest

from conans.client import tools
from conans.client.conf import get_default_settings_yml
from conans.errors import ConanException
from conans.model.settings import Settings
from conans.test.utils.mocks import TestBufferConanOutput


@pytest.mark.tool_visual_studio
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
class VCVarsStoreTest(unittest.TestCase):
    output = TestBufferConanOutput()

    def test_81(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '14'
        settings.arch = 'x86'
        settings.os = 'WindowsStore'
        settings.os.version = '8.1'

        command = tools.vcvars_command(settings, output=self.output)
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('x86', command)
        self.assertIn('store', command)
        self.assertIn('8.1', command)

    def test_10(self):
        sdk_version = tools.find_windows_10_sdk()
        if not sdk_version:
            return

        settings = Settings.loads(get_default_settings_yml())
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '14'
        settings.arch = 'x86'
        settings.os = 'WindowsStore'
        settings.os.version = '10.0'

        command = tools.vcvars_command(settings, output=self.output)
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('x86', command)
        self.assertIn('store', command)
        self.assertIn(sdk_version, command)

    def test_10_custom_winsdk(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '14'
        settings.arch = 'x86'
        settings.os = 'WindowsStore'
        settings.os.version = '10.0'

        sdk_version = '10.0.18362.0'
        command = tools.vcvars_command(settings, winsdk_version=sdk_version, output=self.output)
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('x86', command)
        self.assertIn('store', command)
        self.assertIn(sdk_version, command)

    def test_invalid(self):
        fake_settings_yml = """
        os:
            WindowsStore:
                version: ["666"]
        arch: [x86]
        compiler:
            Visual Studio:
                runtime: [MD, MT, MTd, MDd]
                version: ["8", "9", "10", "11", "12", "14", "15"]

        build_type: [None, Debug, Release]
        """

        settings = Settings.loads(fake_settings_yml)
        settings.compiler = 'Visual Studio'
        settings.compiler.version = '14'
        settings.arch = 'x86'
        settings.os = 'WindowsStore'
        settings.os.version = '666'

        with self.assertRaises(ConanException):
            tools.vcvars_command(settings, output=self.output)
