#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

import platform
import unittest
from nose.plugins.attrib import attr
from conans.model.settings import Settings
from conans.client.conf import default_settings_yml
from conans.errors import ConanException
from conans import tools
from mock import mock


@attr('visual_studio')
@unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
class VCVarsClangClTest(unittest.TestCase):

    def test_simple(self):
        settings = Settings.loads(default_settings_yml)
        settings.compiler = 'clang'
        settings.compiler.version = '5.0'
        settings.arch = 'x86'
        settings.os = 'Windows'

        command = tools.vcvars_command(settings)
        self.assertIn('vcvarsall.bat', command)
        self.assertIn('x86', command)

    def test_no_version(self):
        settings = Settings.loads(default_settings_yml)
        settings.compiler = 'clang'
        settings.arch = 'x86_64'
        settings.os = 'Windows'

        command = tools.vcvars_command(settings)
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
                tools.vcvars_command(settings)
