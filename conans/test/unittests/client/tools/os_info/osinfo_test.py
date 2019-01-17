#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import unittest
from mock import mock

from conans.client.tools import OSInfo, environment_append, CYGWIN, MSYS2, MSYS, remove_from_path
from conans.errors import ConanException


class OSInfoTest(unittest.TestCase):

    def setUp(self):
        self._uname = None
        self._version = None

    def subprocess_check_output_mock(self, cmd, shell):
        if cmd.endswith('"uname"'):
            return self._uname.encode()
        elif cmd.endswith('"uname -r"'):
            return self._version.encode()
        raise ValueError("don't know how to respond to %s" % cmd)

    def test_windows(self):
        self._uname = None
        self._version = None
        with mock.patch("platform.system", mock.MagicMock(return_value='Windows')):
            with mock.patch.object(OSInfo, "get_win_version_name", return_value="Windows 98"):
                with mock.patch.object(OSInfo, "get_win_os_version", return_value="4.0"):
                    with remove_from_path("uname"):
                        with remove_from_path("bash"):
                            # FIXME: bug in environment_append removing variables which aren't exist (another PR)
                            new_env = dict()
                            if 'CONAN_BASH_PATH' in os.environ:
                                new_env['CONAN_BASH_PATH'] = None
                            with environment_append(new_env):
                                self.assertTrue(OSInfo().is_windows)
                                self.assertFalse(OSInfo().is_cygwin)
                                self.assertFalse(OSInfo().is_msys)
                                self.assertFalse(OSInfo().is_linux)
                                self.assertFalse(OSInfo().is_freebsd)
                                self.assertFalse(OSInfo().is_macos)
                                self.assertFalse(OSInfo().is_solaris)

                                with self.assertRaises(ConanException):
                                    OSInfo.uname()
                                self.assertIsNone(OSInfo.detect_windows_subsystem())

    def test_cygwin(self):
        self._uname = 'CYGWIN_NT-10.0'
        self._version = '2.11.2(0.329/5/3)'
        with mock.patch("platform.system", mock.MagicMock(return_value=self._uname)):
            with mock.patch.object(OSInfo, "get_win_version_name", return_value="Windows 98"):
                with mock.patch.object(OSInfo, "get_win_os_version", return_value="4.0"):
                    self.assertTrue(OSInfo().is_windows)
                    self.assertTrue(OSInfo().is_cygwin)
                    self.assertFalse(OSInfo().is_msys)
                    self.assertFalse(OSInfo().is_linux)
                    self.assertFalse(OSInfo().is_freebsd)
                    self.assertFalse(OSInfo().is_macos)
                    self.assertFalse(OSInfo().is_solaris)

                    with environment_append({"CONAN_BASH_PATH": "/fake/bash.exe"}):
                        with mock.patch('subprocess.check_output', new=self.subprocess_check_output_mock):
                            self.assertEqual(OSInfo.uname(), self._uname.lower())
                            self.assertEqual(OSInfo.detect_windows_subsystem(), CYGWIN)

    def test_msys2(self):
        self._uname = 'MSYS_NT-10.0'
        self._version = '1.0.18(0.48/3/2)'
        with mock.patch("platform.system", mock.MagicMock(return_value=self._uname)):
            with mock.patch.object(OSInfo, "get_win_version_name", return_value="Windows 98"):
                with mock.patch.object(OSInfo, "get_win_os_version", return_value="4.0"):
                    self.assertTrue(OSInfo().is_windows)
                    self.assertFalse(OSInfo().is_cygwin)
                    self.assertTrue(OSInfo().is_msys)
                    self.assertFalse(OSInfo().is_linux)
                    self.assertFalse(OSInfo().is_freebsd)
                    self.assertFalse(OSInfo().is_macos)
                    self.assertFalse(OSInfo().is_solaris)

                    with environment_append({"CONAN_BASH_PATH": "/fake/bash.exe"}):
                        with mock.patch('subprocess.check_output', new=self.subprocess_check_output_mock):
                            self.assertEqual(OSInfo.uname(), self._uname.lower())
                            self.assertEqual(OSInfo.detect_windows_subsystem(), MSYS)

    def test_mingw32(self):
        self._uname = 'MINGW32_NT-10.0'
        self._version = '2.10.0(0.325/5/3)'
        with mock.patch("platform.system", mock.MagicMock(return_value=self._uname)):
            with mock.patch.object(OSInfo, "get_win_version_name", return_value="Windows 98"):
                with mock.patch.object(OSInfo, "get_win_os_version", return_value="4.0"):
                    self.assertTrue(OSInfo().is_windows)
                    self.assertFalse(OSInfo().is_cygwin)
                    self.assertTrue(OSInfo().is_msys)
                    self.assertFalse(OSInfo().is_linux)
                    self.assertFalse(OSInfo().is_freebsd)
                    self.assertFalse(OSInfo().is_macos)
                    self.assertFalse(OSInfo().is_solaris)

                    with environment_append({"CONAN_BASH_PATH": "/fake/bash.exe"}):
                        with mock.patch('subprocess.check_output', new=self.subprocess_check_output_mock):
                            self.assertEqual(OSInfo.uname(), self._uname.lower())
                            self.assertEqual(OSInfo.detect_windows_subsystem(), MSYS2)

    def test_mingw64(self):
        self._uname = 'MINGW64_NT-10.0'
        self._version = '2.4.0(0.292/5/3)'
        with mock.patch("platform.system", mock.MagicMock(return_value=self._uname)):
            with mock.patch.object(OSInfo, "get_win_version_name", return_value="Windows 98"):
                with mock.patch.object(OSInfo, "get_win_os_version", return_value="4.0"):
                    self.assertTrue(OSInfo().is_windows)
                    self.assertFalse(OSInfo().is_cygwin)
                    self.assertTrue(OSInfo().is_msys)
                    self.assertFalse(OSInfo().is_linux)
                    self.assertFalse(OSInfo().is_freebsd)
                    self.assertFalse(OSInfo().is_macos)
                    self.assertFalse(OSInfo().is_solaris)

                    with environment_append({"CONAN_BASH_PATH": "/fake/bash.exe"}):
                        with mock.patch('subprocess.check_output', new=self.subprocess_check_output_mock):
                            self.assertEqual(OSInfo.uname(), self._uname.lower())
                            self.assertEqual(OSInfo.detect_windows_subsystem(), MSYS2)

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

                with self.assertRaises(ConanException):
                    OSInfo.uname()
                self.assertIsNone(OSInfo.detect_windows_subsystem())

    def test_macos(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='Darwin')):
            self.assertFalse(OSInfo().is_windows)
            self.assertFalse(OSInfo().is_cygwin)
            self.assertFalse(OSInfo().is_msys)
            self.assertFalse(OSInfo().is_linux)
            self.assertFalse(OSInfo().is_freebsd)
            self.assertTrue(OSInfo().is_macos)
            self.assertFalse(OSInfo().is_solaris)

            with self.assertRaises(ConanException):
                OSInfo.uname()
            self.assertIsNone(OSInfo.detect_windows_subsystem())

    def test_freebsd(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='FreeBSD')):
            self.assertFalse(OSInfo().is_windows)
            self.assertFalse(OSInfo().is_cygwin)
            self.assertFalse(OSInfo().is_msys)
            self.assertFalse(OSInfo().is_linux)
            self.assertTrue(OSInfo().is_freebsd)
            self.assertFalse(OSInfo().is_macos)
            self.assertFalse(OSInfo().is_solaris)

            with self.assertRaises(ConanException):
                OSInfo.uname()
            self.assertIsNone(OSInfo.detect_windows_subsystem())

    def test_solaris(self):
        with mock.patch("platform.system", mock.MagicMock(return_value='SunOS')):
            self.assertFalse(OSInfo().is_windows)
            self.assertFalse(OSInfo().is_cygwin)
            self.assertFalse(OSInfo().is_msys)
            self.assertFalse(OSInfo().is_linux)
            self.assertFalse(OSInfo().is_freebsd)
            self.assertFalse(OSInfo().is_macos)
            self.assertTrue(OSInfo().is_solaris)

            with self.assertRaises(ConanException):
                OSInfo.uname()
            self.assertIsNone(OSInfo.detect_windows_subsystem())
