#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

import unittest
import platform
from mock import mock
from conans.client.conf.detect import detected_os
from nose.plugins.attrib import attr


class DetectedOSTest(unittest.TestCase):
    @attr('windows')
    @unittest.skipUnless(platform.system() == "Windows", "Requires windll module")
    def test_cygwin(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='CYGWIN_NT-10.0')):
            self.assertEqual(detected_os(), "Windows")

    @attr('windows')
    @unittest.skipUnless(platform.system() == "Windows", "Requires windll module")
    def test_msys(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='MSYS_NT-10.0')):
            self.assertEqual(detected_os(), "Windows")

    @attr('windows')
    @unittest.skipUnless(platform.system() == "Windows", "Requires windll module")
    def test_mingw32(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='MINGW32_NT-10.0')):
            self.assertEqual(detected_os(), "Windows")

    @attr('windows')
    @unittest.skipUnless(platform.system() == "Windows", "Requires windll module")
    def test_mingw64(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='MINGW64_NT-10.0')):
            self.assertEqual(detected_os(), "Windows")

    def test_darwin(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='Darwin')):
            self.assertEqual(detected_os(), "Macos")

    @attr('linux')
    @unittest.skipUnless(platform.system() == "Linux", "Requires distro module")
    def test_linux(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='Linux')):
            self.assertEqual(detected_os(), "Linux")

    def test_freebsd(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='FreeBSD')):
            self.assertEqual(detected_os(), "FreeBSD")

    def test_solaris(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='SunOS')):
            self.assertEqual(detected_os(), "SunOS")
