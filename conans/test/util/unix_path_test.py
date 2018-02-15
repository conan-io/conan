#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from conans import tools


class UnixPathTest(unittest.TestCase):

    def test_msys_path(self):
        self.assertEqual('/c/windows/system32', tools.unix_path('C:\\Windows\\System32',
                                                                path_flavor=tools.MSYS2))

    def test_cygwin_path(self):
        self.assertEqual('/cygdrive/c/windows/system32', tools.unix_path('C:\\Windows\\System32',
                                                                         path_flavor=tools.CYGWIN))

    def test_wsl_path(self):
        self.assertEqual('/mnt/c/Windows/System32', tools.unix_path('C:\\Windows\\System32',
                                                                    path_flavor=tools.WSL))

    def test_sfu_path(self):
        self.assertEqual('/dev/fs/C/windows/system32', tools.unix_path('C:\\Windows\\System32',
                                                                       path_flavor=tools.SFU))
