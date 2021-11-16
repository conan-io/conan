#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import platform
import stat
import unittest

from conans import tools
from conans.test.utils.test_files import temp_folder
from conans.util.env import environment_update, get_env
from conans.util.files import mkdir


class WhichTest(unittest.TestCase):
    @staticmethod
    def _touch(filename):
        with open(filename, 'a'):
            pass
        os.utime(filename, None)

    @staticmethod
    def _add_executable_bit(filename):
        if platform.system() != "Windows":
            mode = os.stat(filename).st_mode
            mode |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            os.chmod(filename, stat.S_IMODE(mode))

    def test_which_positive(self):
        tmp_dir = temp_folder()
        ext = "" if platform.system() != "Windows" else ".bat"
        fullname = os.path.join(tmp_dir, 'example%s' % ext)
        self._touch(fullname)
        self._add_executable_bit(fullname)
        with environment_update({'PATH': tmp_dir}):
            self.assertEqual(tools.which('example').lower(), fullname.lower())

    def test_which_negative(self):
        tmp_dir = temp_folder()
        with environment_update({'PATH': tmp_dir}):
            self.assertIsNone(tools.which('example.sh'))

    def test_which_non_executable(self):
        if platform.system() == "Windows":
            """on Windows we always have executable permissions by default"""
            return
        tmp_dir = temp_folder()
        fullname = os.path.join(tmp_dir, 'example.sh')
        self._touch(fullname)
        with environment_update({'PATH': tmp_dir}):
            self.assertIsNone(tools.which('example.sh'))

    def test_which_not_dir(self):
        tmp_dir = temp_folder()
        dev_dir = os.path.join(tmp_dir, "Dev")
        dev_git_dir = os.path.join(dev_dir, "Git")
        mkdir(dev_git_dir)
        with environment_update({'PATH': dev_dir}):
            self.assertEqual(dev_dir, get_env("PATH"))
            self.assertIsNone(tools.which('git'))
