#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

import platform
import unittest
from nose.plugins.attrib import attr
from conans.model.settings import Settings
from conans.client.conf import default_settings_yml
from conans import tools


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
