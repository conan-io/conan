#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

import unittest
from mock import mock
from conans.client.conf.detect import detected_os
from conans.client.tools import OSInfo


class DetectedOSTest(unittest.TestCase):
    def test_windows(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='Windows')):
            with mock.patch.object(OSInfo, "get_win_version_name", return_value="Windows 98"):
                with mock.patch.object(OSInfo, "get_win_os_version", return_value="4.0"):
                    self.assertEqual(detected_os(), "Windows")

    def test_cygwin(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='CYGWIN_NT-10.0')):
            with mock.patch.object(OSInfo, "get_win_version_name", return_value="Windows 98"):
                with mock.patch.object(OSInfo, "get_win_os_version", return_value="4.0"):
                    self.assertEqual(detected_os(), "Windows")

    def test_msys(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='MSYS_NT-10.0')):
            with mock.patch.object(OSInfo, "get_win_version_name", return_value="Windows 98"):
                with mock.patch.object(OSInfo, "get_win_os_version", return_value="4.0"):
                    self.assertEqual(detected_os(), "Windows")

    def test_mingw32(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='MINGW32_NT-10.0')):
            with mock.patch.object(OSInfo, "get_win_version_name", return_value="Windows 98"):
                with mock.patch.object(OSInfo, "get_win_os_version", return_value="4.0"):
                    self.assertEqual(detected_os(), "Windows")

    def test_mingw64(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='MINGW64_NT-10.0')):
            with mock.patch.object(OSInfo, "get_win_version_name", return_value="Windows 98"):
                with mock.patch.object(OSInfo, "get_win_os_version", return_value="4.0"):
                    self.assertEqual(detected_os(), "Windows")

    def test_darwin(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='Darwin')):
            self.assertEqual(detected_os(), "Macos")

    def test_linux(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='Linux')):
            with mock.patch.object(OSInfo, '_get_linux_distro_info'):
                self.assertEqual(detected_os(), "Linux")

    def test_freebsd(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='FreeBSD')):
            self.assertEqual(detected_os(), "FreeBSD")

    def test_solaris(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='SunOS')):
            self.assertEqual(detected_os(), "SunOS")
