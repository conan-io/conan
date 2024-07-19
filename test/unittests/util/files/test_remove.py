# coding=utf-8

import os
import stat
import unittest

from conan.test.utils.test_files import temp_folder
from conans.util.files import remove, save


class RemoveTest(unittest.TestCase):

    def setUp(self):
        self.file = os.path.join(temp_folder(), 'file.txt')
        save(self.file, "some content")

    def test_remove(self):
        remove(self.file)
        self.assertFalse(os.path.exists(self.file))
        self.assertTrue(os.path.exists(os.path.dirname(self.file)))

    def test_remove_readonly(self):
        os.chmod(self.file, stat.S_IREAD|stat.S_IRGRP|stat.S_IROTH)
        with self.assertRaisesRegex((IOError, OSError), "Permission denied"):
            save(self.file, "change the content")
        remove(self.file)
        self.assertFalse(os.path.exists(self.file))
        self.assertTrue(os.path.exists(os.path.dirname(self.file)))

    def test_remove_folder(self):
        dirname = os.path.dirname(self.file)
        self.assertRaises(AssertionError, remove, dirname)
        self.assertTrue(os.path.exists(dirname))

