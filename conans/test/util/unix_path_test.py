#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from conans import tools
from conans.client.tools.win import get_cased_path
from conans.test.utils.test_files import temp_folder
import os
import platform
from conans.util.files import mkdir


class GetCasedPath(unittest.TestCase):
    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def test_case(self):
        folder = temp_folder()
        p1 = os.path.join(folder, "MyFolder", "Subfolder")
        mkdir(p1)
        p2 = get_cased_path(p1)
        self.assertEqual(p1, p2)

        p3 = os.path.join(folder, "myfolder", "subfolder")
        p4 = get_cased_path(p3)
        self.assertEqual(p1, p4)


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
