#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

import unittest
from mock import mock
from conans.client.tools.oss import detected_os, OSInfo
from conans import tools


class DetectedOSTest(unittest.TestCase):
    def test_windows(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='Windows')):
            self.assertEqual(detected_os(), "Windows")

    def test_cygwin(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='CYGWIN_NT-10.0')):
            self.assertEqual(detected_os(), "Windows")

    def test_msys(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='MSYS_NT-10.0')):
            self.assertEqual(detected_os(), "Windows")

    def test_mingw32(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='MINGW32_NT-10.0')):
            self.assertEqual(detected_os(), "Windows")

    def test_mingw64(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='MINGW64_NT-10.0')):
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

    def test_export_tools(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='FreeBSD')):
            self.assertEqual(tools.detected_os(), "FreeBSD")
