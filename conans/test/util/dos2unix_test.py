#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import os
from conans import tools
from conans.test.utils.test_files import temp_folder


class Dos2unixTest(unittest.TestCase):
    @staticmethod
    def _new_dos_file(filename):
        tmp_dir = temp_folder()
        filepath = os.path.join(tmp_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(b'This is a test\r\n')
        return filepath

    def test_successful_conversion(self):
        dos_file = self._new_dos_file('dummy')
        tools.dos2unix(dos_file)
        self.assertTrue(b'\n' in open(dos_file, 'rb').read())
        self.assertFalse(b'\r\n' in open(dos_file, 'rb').read())
