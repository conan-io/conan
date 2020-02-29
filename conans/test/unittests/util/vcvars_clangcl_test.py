#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

import platform
import unittest

from mock import mock
from nose.plugins.attrib import attr

from conans.client.conf import default_settings_yml
from conans.client.tools.win import vcvars_command
from conans.errors import ConanException
from conans.model.settings import Settings
from conans.test.utils.tools import TestBufferConanOutput


@attr('visual_studio')
@unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
class VCVarsClangClTest(unittest.TestCase):
    output = TestBufferConanOutput()

    def test_simple(self):
        settings = Settings.loads(default_settings_yml)
        settings.compiler = 'clang'
        settings.compiler.version = '5.0'
        settings.arch = 'x86'
        settings.os = 'Windows'

        command = vcvars_command(settings, output=self.output)
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('x86', command)

    def test_no_version(self):
        settings = Settings.loads(default_settings_yml)
        settings.compiler = 'clang'
        settings.arch = 'x86_64'
        settings.os = 'Windows'

        command = vcvars_command(settings, output=self.output)
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('amd64', command)

    def test_no_msvc(self):
        settings = Settings.loads(default_settings_yml)
        settings.compiler = 'clang'
        settings.arch = 'x86_64'
        settings.os = 'Windows'

        with mock.patch('conans.client.tools.win.latest_vs_version_installed',
                        mock.MagicMock(return_value=None)):
            with self.assertRaises(ConanException):
                vcvars_command(settings, output=self.output)
