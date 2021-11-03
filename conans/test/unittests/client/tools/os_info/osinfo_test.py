#!/usr/bin/env python
# -*- coding: utf-8 -*-

import mock
import unittest

from conans.client.tools import OSInfo, environment_append


class OSInfoTest(unittest.TestCase):

    def setUp(self):
        self._uname = None
        self._version = None

    def subprocess_check_output_mock(self, cmd):
        if cmd.endswith('"uname"'):
            return self._uname
        elif cmd.endswith('"uname -r"'):
            return self._version
        elif cmd.endswith('oslevel'):
            return self._version
        raise ValueError("don't know how to respond to %s" % cmd)

    def test_windows(self):
        self._uname = None
        self._version = None
        with mock.patch("platform.system", mock.MagicMock(return_value='Windows')):
            self.assertTrue(OSInfo().is_windows)
            self.assertFalse(OSInfo().is_cygwin)
            self.assertFalse(OSInfo().is_msys)
            self.assertFalse(OSInfo().is_linux)
            self.assertFalse(OSInfo().is_freebsd)
            self.assertFalse(OSInfo().is_macos)
            self.assertFalse(OSInfo().is_solaris)
            self.assertFalse(OSInfo().is_aix)

    def test_cygwin(self):
        self._uname = 'CYGWIN_NT-10.0'
        self._version = '2.11.2(0.329/5/3)'
        with mock.patch("platform.system", mock.MagicMock(return_value=self._uname)):
            self.assertTrue(OSInfo().is_windows)
            self.assertTrue(OSInfo().is_cygwin)
            self.assertFalse(OSInfo().is_msys)
            self.assertFalse(OSInfo().is_linux)
            self.assertFalse(OSInfo().is_freebsd)
            self.assertFalse(OSInfo().is_macos)
            self.assertFalse(OSInfo().is_solaris)
            self.assertFalse(OSInfo().is_aix)

    def test_msys2(self):
        self._uname = 'MSYS_NT-10.0'
        self._version = '1.0.18(0.48/3/2)'
        with mock.patch("platform.system", mock.MagicMock(return_value=self._uname)):
            self.assertTrue(OSInfo().is_windows)
            self.assertFalse(OSInfo().is_cygwin)
            self.assertTrue(OSInfo().is_msys)
            self.assertFalse(OSInfo().is_linux)
            self.assertFalse(OSInfo().is_freebsd)
            self.assertFalse(OSInfo().is_macos)
            self.assertFalse(OSInfo().is_solaris)
            self.assertFalse(OSInfo().is_aix)

    def test_msys3(self):
        self._uname = 'MSYS_NT-10.0'
        self._version = '3.0.6(0.338/5/3)'
        with mock.patch("platform.system", mock.MagicMock(return_value=self._uname)):
            self.assertTrue(OSInfo().is_windows)
            self.assertFalse(OSInfo().is_cygwin)
            self.assertTrue(OSInfo().is_msys)
            self.assertFalse(OSInfo().is_linux)
            self.assertFalse(OSInfo().is_freebsd)
            self.assertFalse(OSInfo().is_macos)
            self.assertFalse(OSInfo().is_solaris)

    def test_mingw32(self):
        self._uname = 'MINGW32_NT-10.0'
        self._version = '2.10.0(0.325/5/3)'
        with mock.patch("platform.system", mock.MagicMock(return_value=self._uname)):
            self.assertTrue(OSInfo().is_windows)
            self.assertFalse(OSInfo().is_cygwin)
            self.assertTrue(OSInfo().is_msys)
            self.assertFalse(OSInfo().is_linux)
            self.assertFalse(OSInfo().is_freebsd)
            self.assertFalse(OSInfo().is_macos)
            self.assertFalse(OSInfo().is_solaris)
            self.assertFalse(OSInfo().is_aix)

    def test_mingw64(self):
        self._uname = 'MINGW64_NT-10.0'
        self._version = '2.4.0(0.292/5/3)'
        with mock.patch("platform.system", mock.MagicMock(return_value=self._uname)):
            self.assertTrue(OSInfo().is_windows)
            self.assertFalse(OSInfo().is_cygwin)
            self.assertTrue(OSInfo().is_msys)
            self.assertFalse(OSInfo().is_linux)
            self.assertFalse(OSInfo().is_freebsd)
            self.assertFalse(OSInfo().is_macos)
            self.assertFalse(OSInfo().is_solaris)
            self.assertFalse(OSInfo().is_aix)

    def test_linux(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='Linux')):
            with mock.patch.object(OSInfo, '_get_linux_distro_info'):
                self.assertFalse(OSInfo().is_windows)
                self.assertFalse(OSInfo().is_cygwin)
                self.assertFalse(OSInfo().is_msys)
                self.assertTrue(OSInfo().is_linux)
                self.assertFalse(OSInfo().is_freebsd)
                self.assertFalse(OSInfo().is_macos)
                self.assertFalse(OSInfo().is_solaris)
                self.assertFalse(OSInfo().is_aix)

    def test_macos(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='Darwin')):
            self.assertFalse(OSInfo().is_windows)
            self.assertFalse(OSInfo().is_cygwin)
            self.assertFalse(OSInfo().is_msys)
            self.assertFalse(OSInfo().is_linux)
            self.assertFalse(OSInfo().is_freebsd)
            self.assertTrue(OSInfo().is_macos)
            self.assertFalse(OSInfo().is_solaris)
            self.assertFalse(OSInfo().is_aix)

    def test_freebsd(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='FreeBSD')):
            self.assertFalse(OSInfo().is_windows)
            self.assertFalse(OSInfo().is_cygwin)
            self.assertFalse(OSInfo().is_msys)
            self.assertFalse(OSInfo().is_linux)
            self.assertTrue(OSInfo().is_freebsd)
            self.assertFalse(OSInfo().is_macos)
            self.assertFalse(OSInfo().is_solaris)
            self.assertFalse(OSInfo().is_aix)

    def test_solaris(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='SunOS')):
            self.assertFalse(OSInfo().is_windows)
            self.assertFalse(OSInfo().is_cygwin)
            self.assertFalse(OSInfo().is_msys)
            self.assertFalse(OSInfo().is_linux)
            self.assertFalse(OSInfo().is_freebsd)
            self.assertFalse(OSInfo().is_macos)
            self.assertTrue(OSInfo().is_solaris)
            self.assertFalse(OSInfo().is_aix)

    def test_wsl(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='Linux')):
            with mock.patch.object(OSInfo, '_get_linux_distro_info'):
                self.assertFalse(OSInfo().is_windows)
                self.assertFalse(OSInfo().is_cygwin)
                self.assertFalse(OSInfo().is_msys)
                self.assertTrue(OSInfo().is_linux)
                self.assertFalse(OSInfo().is_freebsd)
                self.assertFalse(OSInfo().is_macos)
                self.assertFalse(OSInfo().is_solaris)

    def test_aix(self):
        self._uname = 'AIX'
        self._version = '7.1.0.0'

        with mock.patch("platform.system", mock.MagicMock(return_value='AIX')), \
                mock.patch('conans.client.tools.oss.check_output_runner',
                           new=self.subprocess_check_output_mock):
            self.assertFalse(OSInfo().is_windows)
            self.assertFalse(OSInfo().is_cygwin)
            self.assertFalse(OSInfo().is_msys)
            self.assertFalse(OSInfo().is_linux)
            self.assertFalse(OSInfo().is_freebsd)
            self.assertFalse(OSInfo().is_macos)
            self.assertFalse(OSInfo().is_solaris)
            self.assertTrue(OSInfo().is_aix)

            self.assertEqual(OSInfo().os_version_name, 'AIX 7.1')
