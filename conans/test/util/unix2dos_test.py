#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import os
from conans import tools
from conans.test.utils.test_files import temp_folder


class Unix2dosTest(unittest.TestCase):
    @staticmethod
    def _new_unix_file(filename):
        tmp_dir = temp_folder()
        filepath = os.path.join(tmp_dir, filename)
        with open(filepath, 'w') as f:
            f.write('This is a test\n')
        return filepath

    def test_successful_conversion(self):
        unix_file = self._new_unix_file('dummy')
        tools.unix2dos(unix_file)
        self.assertTrue('\r\n' in open(unix_file, 'rb').read().decode())
