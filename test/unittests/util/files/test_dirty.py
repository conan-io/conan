# coding=utf-8

import os
import unittest


from conan.test.utils.test_files import temp_folder
from conans.util.files import set_dirty, clean_dirty, set_dirty_context_manager, _DIRTY_FOLDER


class DirtyTest(unittest.TestCase):

    def setUp(self):
        """ Create temporary folder to save dirty state

        """
        self.temp_folder = temp_folder()
        self.dirty_folder = self.temp_folder + _DIRTY_FOLDER

    def test_set_dirty(self):
        """ Dirty flag must be created by set_dirty

        """
        set_dirty(self.temp_folder)
        self.assertTrue(os.path.exists(self.dirty_folder))

    def test_clean_dirty(self):
        """ Dirty flag must be cleaned by clean_dirty

        """
        set_dirty(self.temp_folder)
        self.assertTrue(os.path.exists(self.dirty_folder))
        clean_dirty(self.temp_folder)
        self.assertFalse(os.path.exists(self.dirty_folder))

    def test_set_dirty_context(self):
        """ Dirty context must remove lock before exiting

        """
        with set_dirty_context_manager(self.temp_folder):
            self.assertTrue(os.path.exists(self.dirty_folder))
        self.assertFalse(os.path.exists(self.dirty_folder))

    def test_interrupted_dirty_context(self):
        """ Broken context must preserve dirty state

            Raise an exception in middle of context. By default,
            dirty file is not removed.
        """
        try:
            with set_dirty_context_manager(self.temp_folder):
                self.assertTrue(os.path.exists(self.dirty_folder))
                raise RuntimeError()
        except RuntimeError:
            pass
        self.assertTrue(os.path.exists(self.dirty_folder))
