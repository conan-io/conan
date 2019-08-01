# -*- coding: utf-8 -*-

import os
import unittest

from parameterized import parameterized

from conans.util.files import load


class LoadTest(unittest.TestCase):

    @parameterized.expand([("conanfile_utf8.txt",),
                           ("conanfile_utf8_with_bom.txt",),
                           ("conanfile_utf16le_with_bom.txt",),
                           ("conanfile_utf16be_with_bom.txt",)])
    def test_encoding(self, filename):
        path = os.path.join(os.path.dirname(__file__), "data", filename)
        contents = load(path)
        self.assertTrue(contents.startswith("[requires]"))
