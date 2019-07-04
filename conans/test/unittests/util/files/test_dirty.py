# coding=utf-8

import os
import unittest


from conans.test.utils.test_files import temp_folder
from conans.util.files import set_dirty, clean_dirty, set_dirty_context_manager, _DIRTY_FOLDER


class DirtyTest(unittest.TestCase):

    def setUp(self):
        self.temp_folder = temp_folder()
        self.dirty_folder = self.temp_folder + _DIRTY_FOLDER

    def test_set_dirty(self):
        set_dirty(self.temp_folder)
        self.assertTrue(os.path.exists(self.dirty_folder))

    def test_clean_dirty(self):
        set_dirty(self.temp_folder)
        self.assertTrue(os.path.exists(self.dirty_folder))
        clean_dirty(self.temp_folder)
        self.assertFalse(os.path.exists(self.dirty_folder))

    def test_set_dirty_context(self):
        with set_dirty_context_manager(self.temp_folder):
            self.assertTrue(os.path.exists(self.dirty_folder))
        self.assertFalse(os.path.exists(self.dirty_folder))

        try:
            with set_dirty_context_manager(self.temp_folder):
                self.assertTrue(os.path.exists(self.dirty_folder))
                self.fail()
        except AssertionError:
            pass
        self.assertTrue(os.path.exists(self.dirty_folder))
