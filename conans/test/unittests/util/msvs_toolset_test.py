#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from parameterized import parameterized

from conans.client import tools
from conans.test.utils.mocks import MockSettings


class MSVCToolsetTest(unittest.TestCase):

    @parameterized.expand([("17", "v143"),
                           ("16", "v142"),
                           ("15", "v141"),
                           ("14", "v140"),
                           ("12", "v120"),
                           ("11", "v110"),
                           ("10", "v100"),
                           ("9", "v90"),
                           ("8", "v80")])
    def test_default(self, compiler_version, expected_toolset):
        settings = MockSettings({"compiler": "Visual Studio",
                                 "compiler.version": compiler_version})
        self.assertEqual(expected_toolset, tools.msvs_toolset(settings))

    @parameterized.expand([("16", "v141_xp"),
                           ("15", "v141_xp"),
                           ("14", "v140_xp"),
                           ("12", "v120_xp"),
                           ("11", "v110_xp")])
    def test_custom(self, compiler_version, expected_toolset):
        settings = MockSettings({"compiler": "Visual Studio",
                                 "compiler.version": compiler_version,
                                 "compiler.toolset": expected_toolset})
        self.assertEqual(expected_toolset, tools.msvs_toolset(settings))

    def test_negative(self):
        self.assertIsNone(tools.msvs_toolset(MockSettings({"compiler": "Visual Studio",
                                                           "compiler.version": "666"})))
