#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import os
from conans import tools
from conans.test.utils.test_files import temp_folder

def new_unix_file(filename):
    tmp_dir = temp_folder()
    filepath = os.path.join(tmp_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(b'This is a test\n')
    return filepath

def new_dos_file(filename):
    tmp_dir = temp_folder()
    filepath = os.path.join(tmp_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(b'This is a test\r\n')
    return filepath

class Unix2dosTest(unittest.TestCase):
    def test_successful_conversion(self):
        unix_file = new_unix_file('unix_file1')
        tools.unix2dos(unix_file)
        self.assertTrue(b'\r\n' in open(unix_file, 'rb').read())

    def test_ignored_conversion(self):
        dos_file = new_dos_file('dos_file1')
        self.assertFalse(tools.unix2dos(dos_file))

class Dos2unixTest(unittest.TestCase):
    def test_successful_conversion(self):
        dos_file = new_dos_file('dos_file2')
        self.assertTrue(tools.dos2unix(dos_file))
        self.assertTrue(b'\n' in open(dos_file, 'rb').read())
        self.assertFalse(b'\r\n' in open(dos_file, 'rb').read())

    def test_ignored_conversion(self):
        unix_file = new_unix_file('unix_file2')
        self.assertFalse(tools.dos2unix(unix_file))
