#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from collections import namedtuple

from mock import mock

from conans.client.tools.oss import get_cross_building_settings, OSInfo
from conans.test.utils.mocks import MockSettings

# TODO: Add tests using settings_host and settings_build

MockConanfile = namedtuple('ConanFileMock', ['settings'])


class GetCrossBuildSettingsTest(unittest.TestCase):
    def test_windows(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='Windows')),\
             mock.patch("platform.machine", mock.MagicMock(return_value="x86_64")),\
             mock.patch.object(OSInfo, "get_win_version_name", return_value="Windows 98"),\
             mock.patch.object(OSInfo, "get_win_os_version", return_value="4.0"):
            conanfile = MockConanfile(MockSettings({}))
            build_os, build_arch, _, _ = get_cross_building_settings(conanfile)
            self.assertEqual("Windows", build_os)
            self.assertEqual("x86_64", build_arch)

    def test_cygwin(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='CYGWIN_NT-10.0')), \
             mock.patch("platform.machine", mock.MagicMock(return_value="x86_64")), \
             mock.patch.object(OSInfo, "get_win_version_name", return_value="Windows 98"), \
             mock.patch.object(OSInfo, "get_win_os_version", return_value="4.0"):
            conanfile = MockConanfile(MockSettings({}))
            build_os, build_arch, _, _ = get_cross_building_settings(conanfile)
            self.assertEqual("Windows", build_os)
            self.assertEqual("x86_64", build_arch)

    def test_msys(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='MSYS_NT-10.0')), \
             mock.patch("platform.machine", mock.MagicMock(return_value="x86_64")), \
             mock.patch.object(OSInfo, "get_win_version_name", return_value="Windows 98"), \
             mock.patch.object(OSInfo, "get_win_os_version", return_value="4.0"):
            conanfile = MockConanfile(MockSettings({}))
            build_os, build_arch, _, _ = get_cross_building_settings(conanfile)
            self.assertEqual("Windows", build_os)
            self.assertEqual("x86_64", build_arch)

    def test_mingw32(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='MINGW32_NT-10.0')), \
             mock.patch("platform.machine", mock.MagicMock(return_value="x86_64")), \
             mock.patch.object(OSInfo, "get_win_version_name", return_value="Windows 98"), \
             mock.patch.object(OSInfo, "get_win_os_version", return_value="4.0"):
            conanfile = MockConanfile(MockSettings({}))
            build_os, build_arch, _, _ = get_cross_building_settings(conanfile)
            self.assertEqual("Windows", build_os)
            self.assertEqual("x86_64", build_arch)

    def test_mingw64(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='MINGW64_NT-10.0')), \
             mock.patch("platform.machine", mock.MagicMock(return_value="x86_64")), \
             mock.patch.object(OSInfo, "get_win_version_name", return_value="Windows 98"), \
             mock.patch.object(OSInfo, "get_win_os_version", return_value="4.0"):
            conanfile = MockConanfile(MockSettings({}))
            build_os, build_arch, _, _ = get_cross_building_settings(conanfile)
            self.assertEqual("Windows", build_os)
            self.assertEqual("x86_64", build_arch)

    def test_linux(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='Linux')), \
             mock.patch("platform.machine", mock.MagicMock(return_value="x86_64")), \
             mock.patch.object(OSInfo, '_get_linux_distro_info'):
            conanfile = MockConanfile(MockSettings({}))
            build_os, build_arch, _, _ = get_cross_building_settings(conanfile)
            self.assertEqual("Linux", build_os)
            self.assertEqual("x86_64", build_arch)

    def test_macos(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='Darwin')), \
             mock.patch("platform.machine", mock.MagicMock(return_value="x86_64")):
            conanfile = MockConanfile(MockSettings({}))
            build_os, build_arch, _, _ = get_cross_building_settings(conanfile)
            self.assertEqual("Macos", build_os)
            self.assertEqual("x86_64", build_arch)

    def test_freebsd(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='FreeBSD')), \
             mock.patch("platform.machine", mock.MagicMock(return_value="x86_64")):
            conanfile = MockConanfile(MockSettings({}))
            build_os, build_arch, _, _ = get_cross_building_settings(conanfile)
            self.assertEqual("FreeBSD", build_os)
            self.assertEqual("x86_64", build_arch)

    def test_solaris(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='SunOS')), \
             mock.patch("platform.machine", mock.MagicMock(return_value="x86_64")):
            conanfile = MockConanfile(MockSettings({}))
            build_os, build_arch, _, _ = get_cross_building_settings(conanfile)
            self.assertEqual("SunOS", build_os)
            self.assertEqual("x86_64", build_arch)

    def test_aix(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='AIX')), \
             mock.patch("platform.machine", mock.MagicMock(return_value="x86_64")):
            conanfile = MockConanfile(MockSettings({}))
            build_os, build_arch, _, _ = get_cross_building_settings(conanfile)
            self.assertEqual("AIX", build_os)
            self.assertEqual("x86_64", build_arch)

    def test_vxworks(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='VxWorks')), \
             mock.patch("platform.machine", mock.MagicMock(return_value="armv7")):
            conanfile = MockConanfile(MockSettings({}))
            build_os, build_arch, _, _ = get_cross_building_settings(conanfile)
            self.assertEqual("VxWorks", build_os)
            self.assertEqual("armv7", build_arch)
