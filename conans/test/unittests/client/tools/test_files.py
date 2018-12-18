# coding=utf-8

import os
import shutil
import tempfile
import unittest

from conans.client.tools.files import dot_clean, save, chdir


class DotCleanTest(unittest.TestCase):

    def setUp(self):
        tmp_folder = tempfile.mkdtemp()

        def cleanup():
            shutil.rmtree(tmp_folder)

        self.addCleanup(cleanup)
        self.tmp_folder = tmp_folder

    def _run_test(self, tuples):
        with chdir(self.tmp_folder):
            for f, _ in tuples:
                save(f, "")

            dot_clean(".")

            for f, expected_after in tuples:
                self.assertEqual(expected_after, os.path.exists(f))

    def test_removal_normal(self):
        files = [("file.txt", True),
                 ("._file.txt", False),
                 ("folder/file.txt", True),
                 ("folder/._file.txt", False),]
        self._run_test(tuples=files)

    def test_only_remove_matching_ones(self):
        files = [("file.txt", True),
                 ("._file.txt", False),
                 ("._other.txt", True)]
        self._run_test(tuples=files)

    def test_handle_dirs(self):
        files = [("folder/file.txt", True),
                 ("folder/._file.txt", False),
                 ("._folder/file.txt", True),
                 ("._folder/._file.txt", False),
                 ("._other/._file.txt", True),
                 ("._other2/file.txt", True)]
        self._run_test(tuples=files)
