import os
import shutil
import unittest
from os.path import join

import pytest

from conans.errors import ConanException
from conan.test.utils.test_files import temp_folder
from conans.util.files import mkdir, save, merge_directories, load


class MergeDirectoriesTest(unittest.TestCase):

    def setUp(self):
        self.source = temp_folder()
        self.dest = temp_folder()

    def _save(self, folder, files, content=None):
        for the_file in files:
            save(join(folder, the_file), content or "c")

    def _get_paths(self, folder):
        ret = []
        for root, dirs, files in os.walk(folder):
            for the_file in files:
                relpath = os.path.relpath(root, folder)
                if relpath == ".":
                    relpath = ""
                ret.append(join(relpath, the_file))
            for the_dir in dirs:
                if not os.listdir(join(root, the_dir)):
                    relpath = os.path.relpath(join(root, the_dir), folder)
                    ret.append(relpath)
        return ret

    def _assert_equals(self, list1, list2):
        self.assertEqual(set([el.replace("/", "\\") for el in list1]),
                          set([el.replace("/", "\\") for el in list2]))

    def test_empty_dest_merge(self):
        files = ["file.txt", "subdir/file2.txt"]
        self._save(self.source, files)
        merge_directories(self.source, self.dest)
        self._assert_equals(self._get_paths(self.dest), files)

    def test_non_empty_dest_merge(self):
        files = ["file.txt", "subdir/file2.txt"]
        self._save(self.source, files, "fromsrc")

        files_dest = ["file.txt", "subdir2/file2.txt"]
        self._save(self.dest, files_dest, "fromdest")

        merge_directories(self.source, self.dest)
        self._assert_equals(self._get_paths(self.dest), files + files_dest)
        # File from src overrides file from dest
        self.assertEqual(load(join(self.dest, "file.txt")), "fromsrc")

    def test_nested_directories(self):
        self.dest = join(self.source, "destination_dir")
        files_dest = ["file.txt", "subdir2/file2.txt"]
        self._save(self.dest, files_dest, "fromdest")
        mkdir(join(self.dest, "empty_folder", "subempty_folder"))

        files = ["file.txt", "subdir/file2.txt"]
        self._save(self.source, files, "fromsrc")

        merge_directories(self.source, self.dest)
        self._assert_equals(self._get_paths(self.dest), files + files_dest +
                            ['empty_folder/subempty_folder', ])
        self.assertEqual(load(join(self.dest, "file.txt")), "fromsrc")
        self.assertEqual(load(join(self.dest, "subdir2/file2.txt")), "fromdest")
        self.assertEqual(load(join(self.dest, "subdir/file2.txt")), "fromsrc")

    def test_same_directory(self):
        # Same directory cannot be merged, this should never happen
        with pytest.raises(ConanException):
            merge_directories(self.source, self.source)

    def test_parent_directory(self):
        files_dest = ["file.txt", "subdir2/file2.txt"]
        self._save(self.dest, files_dest, "fromdest")
        self.source = join(self.dest, "source_folder")
        files = ["file.txt", "subdir/file2.txt"]
        self._save(self.source, files, "fromsrc")
        merge_directories(self.source, self.dest)
        shutil.rmtree(self.source)
        self._assert_equals(self._get_paths(self.dest), files + files_dest)
        self.assertEqual(load(join(self.dest, "file.txt")), "fromsrc")
        self.assertEqual(load(join(self.dest, "subdir2/file2.txt")), "fromdest")
        self.assertEqual(load(join(self.dest, "subdir/file2.txt")), "fromsrc")
