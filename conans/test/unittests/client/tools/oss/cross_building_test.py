# -*- coding: utf-8 -*-

import unittest

from mock import mock

from conans.client.conf import get_default_settings_yml
from conans.client.tools.oss import cross_building
from conans.model.settings import Settings


# TODO: Add tests using a conanfile with 'settings' and 'settings_build'

class CrossBuildingTest(unittest.TestCase):
    def test_same(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "FreeBSD"
        settings.arch = "x86_64"
        settings.arch_build = "x86_64"
        self.assertFalse(cross_building(settings, self_os="FreeBSD", self_arch="x86_64"))

        with mock.patch("platform.system", mock.MagicMock(return_value='FreeBSD')),\
             mock.patch("platform.machine", mock.MagicMock(return_value="x86_64")):
            self.assertFalse(cross_building(settings))

        settings.os_build = "FreeBSD"
        settings.arch = "x86_64"
        self.assertFalse(cross_building(settings))

    def test_different_os(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Linux"
        settings.arch = "x86_64"
        self.assertTrue(cross_building(settings, self_os="FreeBSD", self_arch="x86_64"))

        with mock.patch("platform.system", mock.MagicMock(return_value='FreeBSD')),\
             mock.patch("platform.machine", mock.MagicMock(return_value="x86_64")):
            self.assertTrue(cross_building(settings))

        settings.os_build = "FreeBSD"
        settings.arch_build = "x86_64"
        self.assertTrue(cross_building(settings))

    def test_different_arch(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "FreeBSD"
        settings.arch = "x86"
        self.assertTrue(cross_building(settings, self_os="FreeBSD", self_arch="x86_64"))

        with mock.patch("platform.system", mock.MagicMock(return_value='FreeBSD')), \
             mock.patch("platform.machine", mock.MagicMock(return_value="x86_64")):
            self.assertTrue(cross_building(settings))

        settings.os_build = "FreeBSD"
        settings.arch_build = "x86_64"
        self.assertTrue(cross_building(settings))

    def test_x64_x86(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "FreeBSD"
        settings.arch = "x86"
        self.assertFalse(cross_building(settings,  self_os="FreeBSD",
                                        self_arch="x86_64", skip_x64_x86=True))
        self.assertTrue(cross_building(settings, self_os="FreeBSD",
                                       self_arch="x86_64", skip_x64_x86=False))

        with mock.patch("platform.system", mock.MagicMock(return_value='FreeBSD')), \
             mock.patch("platform.machine", mock.MagicMock(return_value="x86_64")):
            self.assertFalse(cross_building(settings, skip_x64_x86=True))
            self.assertTrue(cross_building(settings, skip_x64_x86=False))

        settings.os_build = "FreeBSD"
        settings.arch_build = "x86_64"
        self.assertFalse(cross_building(settings, skip_x64_x86=True))
        self.assertTrue(cross_building(settings, skip_x64_x86=False))

    def test_x86_x64(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "FreeBSD"
        settings.arch = "x86_64"
        self.assertTrue(cross_building(settings,  self_os="FreeBSD",
                                       self_arch="x86", skip_x64_x86=True))
        self.assertTrue(cross_building(settings, self_os="FreeBSD",
                                       self_arch="x86", skip_x64_x86=False))

        with mock.patch("platform.system", mock.MagicMock(return_value='FreeBSD')), \
             mock.patch("platform.machine", mock.MagicMock(return_value="x86")):
            self.assertTrue(cross_building(settings, skip_x64_x86=True))
            self.assertTrue(cross_building(settings, skip_x64_x86=False))

        settings.os_build = "FreeBSD"
        settings.arch_build = "x86"
        self.assertTrue(cross_building(settings, skip_x64_x86=True))
        self.assertTrue(cross_building(settings, skip_x64_x86=False))

    def test_x86_64_different_os(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Linux"
        settings.arch = "x86"
        self.assertTrue(cross_building(settings,  self_os="FreeBSD",
                                       self_arch="x86_64", skip_x64_x86=True))
        self.assertTrue(cross_building(settings, self_os="FreeBSD",
                                       self_arch="x86_64", skip_x64_x86=False))

        with mock.patch("platform.system", mock.MagicMock(return_value='FreeBSD')), \
             mock.patch("platform.machine", mock.MagicMock(return_value="x86_64")):
            self.assertTrue(cross_building(settings, skip_x64_x86=True))
            self.assertTrue(cross_building(settings, skip_x64_x86=False))

        settings.os_build = "FreeBSD"
        settings.arch_build = "x86_64"
        self.assertTrue(cross_building(settings, skip_x64_x86=True))
        self.assertTrue(cross_building(settings, skip_x64_x86=False))
