# coding=utf-8

import os
import unittest

from conans.client.tools.files import save, chdir
from conans.client.tools import apple_dot_clean
from conans.test.utils.test_files import temp_folder


class DotCleanTest(unittest.TestCase):

    def _run_test(self, tuples):
        tmp_folder = temp_folder()
        with chdir(tmp_folder):
            for f, _ in tuples:
                save(f, "")

            apple_dot_clean(".")

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
