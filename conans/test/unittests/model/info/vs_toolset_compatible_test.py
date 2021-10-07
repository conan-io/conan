#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from parameterized import parameterized

from conans.client.conf import get_default_settings_yml
from conans.model.info import ConanInfo
from conans.model.settings import Settings


class VSToolsetCompatibleTest(unittest.TestCase):
    @parameterized.expand([("16", "v143", "17"),
                           ("15", "v142", "16"),
                           ("14", "v141", "15"),
                           ("15", "v140", "14"),
                           ("11", "v120", "12"),
                           ("12", "v110", "11"),
                           ("9", "v100", "10"),
                           ("10", "v90", "9")])
    def test_compatible(self, initial_version, toolset, expected_version):
        info = ConanInfo()
        settings = Settings.loads(get_default_settings_yml())
        info.settings = settings
        settings.compiler = "Visual Studio"
        settings.compiler.toolset = toolset
        settings.compiler.version = initial_version
        info.full_settings = info.settings
        info.vs_toolset_compatible()
        self.assertEqual(info.settings.compiler.version, expected_version)
        self.assertIsNone(info.settings.get_safe("compiler.toolset"))

    @parameterized.expand([("16", "v141_xp"),
                           ("14", "v141_xp"),
                           ("15", "v140_xp"),
                           ("11", "v120_xp"),
                           ("12", "v110_xp"),
                           ("9", "LLVM-vs2012_xp"),
                           ("10", "LLVM-vs2013_xp")])
    def test_incompatible(self, initial_version, toolset):
        info = ConanInfo()
        settings = Settings.loads(get_default_settings_yml())
        info.settings = settings
        settings.compiler = "Visual Studio"
        settings.compiler.toolset = toolset
        settings.compiler.version = initial_version
        info.full_settings = info.settings
        info.vs_toolset_compatible()
        self.assertEqual(info.settings.compiler.version, initial_version)
        self.assertEqual(info.settings.compiler.toolset, toolset)
