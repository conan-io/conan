#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import os
import stat
import platform
from conans import tools
from conans.test.utils.test_files import temp_folder


class WhichTest(unittest.TestCase):
    @staticmethod
    def _touch(filename):
        with open(filename, 'a'):
            os.utime(filename, None)

    @staticmethod
    def _add_executable_bit(filename):
        if os.name == 'posix':
            mode = os.stat(filename).st_mode
            mode |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
            os.chmod(filename, stat.S_IMODE(mode))

    def test_which_positive(self):
        tmp_dir = temp_folder()
        ext = ".sh" if platform.system() != "Windows" else ".bat"
        fullname = os.path.join(tmp_dir, 'example%s' % ext)
        self._touch(fullname)
        self._add_executable_bit(fullname)
        with tools.environment_append({'PATH': tmp_dir}):
            self.assertEqual(tools.which('example').lower(), fullname.lower())

    def test_which_negative(self):
        tmp_dir = temp_folder()
        with tools.environment_append({'PATH': tmp_dir}):
            self.assertIsNone(tools.which('example.sh'))

    def test_which_non_executable(self):
        if platform.system() == "Windows":
            """on Windows we always have executable permissions by default"""
            return
        tmp_dir = temp_folder()
        fullname = os.path.join(tmp_dir, 'example.sh')
        self._touch(fullname)
        with tools.environment_append({'PATH': tmp_dir}):
            self.assertIsNone(tools.which('example.sh'))
