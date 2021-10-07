#!/usr/bin/env python
# -*- coding: utf-8 -*-

import platform
import unittest

import pytest
from mock import mock

from conans.client.conf import get_default_settings_yml
from conans.client.tools.win import vcvars_command
from conans.errors import ConanException
from conans.model.settings import Settings
from conans.test.utils.mocks import TestBufferConanOutput


@pytest.mark.tool_visual_studio
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
class VCVarsClangClTest(unittest.TestCase):
    output = TestBufferConanOutput()

    def test_simple(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.compiler = 'clang'
        settings.compiler.version = '5.0'
        settings.arch = 'x86'
        settings.os = 'Windows'

        command = vcvars_command(settings, output=self.output)
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('x86', command)

    def test_no_version(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.compiler = 'clang'
        settings.arch = 'x86_64'
        settings.os = 'Windows'

        command = vcvars_command(settings, output=self.output)
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('amd64', command)

    def test_no_msvc(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.compiler = 'clang'
        settings.arch = 'x86_64'
        settings.os = 'Windows'

        with mock.patch('conans.client.tools.win.latest_vs_version_installed',
                        mock.MagicMock(return_value=None)):
            with self.assertRaises(ConanException):
                vcvars_command(settings, output=self.output)
