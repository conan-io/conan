# coding=utf-8
import unittest
import os

from os.path import join

from conans import load
from conans.client.source import merge_directories
from conans.util.files import save, mkdir
from conans.test.utils.test_files import temp_folder
import shutil


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
        self.assertEquals(set([el.replace("/", "\\") for el in list1]),
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
        self.assertEquals(load(join(self.dest, "file.txt")), "fromsrc")

    def nested_directories_test(self):
        self.dest = join(self.source, "destination_dir")
        files_dest = ["file.txt", "subdir2/file2.txt"]
        self._save(self.dest, files_dest, "fromdest")
        mkdir(join(self.dest, "empty_folder", "subempty_folder"))

        files = ["file.txt", "subdir/file2.txt"]
        self._save(self.source, files, "fromsrc")

        merge_directories(self.source, self.dest)
        self._assert_equals(self._get_paths(self.dest), files + files_dest +
                            ['empty_folder/subempty_folder', ])
        self.assertEquals(load(join(self.dest, "file.txt")), "fromsrc")
        self.assertEquals(load(join(self.dest, "subdir2/file2.txt")), "fromdest")
        self.assertEquals(load(join(self.dest, "subdir/file2.txt")), "fromsrc")

    def same_directory_test(self):
        files = ["file.txt", "subdir/file2.txt"]
        self._save(self.source, files, "fromsrc")
        merge_directories(self.source, self.source)
        self._assert_equals(self._get_paths(self.source), files)

    def parent_directory_test(self):
        files_dest = ["file.txt", "subdir2/file2.txt"]
        self._save(self.dest, files_dest, "fromdest")
        self.source = join(self.dest, "source_folder")
        files = ["file.txt", "subdir/file2.txt"]
        self._save(self.source, files, "fromsrc")
        merge_directories(self.source, self.dest)
        shutil.rmtree(self.source)
        self._assert_equals(self._get_paths(self.dest), files + files_dest)
        self.assertEquals(load(join(self.dest, "file.txt")), "fromsrc")
        self.assertEquals(load(join(self.dest, "subdir2/file2.txt")), "fromdest")
        self.assertEquals(load(join(self.dest, "subdir/file2.txt")), "fromsrc")

    def excluded_dirs_test(self):
        files = ["file.txt", "subdir/file2.txt", "subdir/file3.txt", "other_dir/somefile.txt",
                 "other_dir/somefile2.txt"]
        self._save(self.source, files, "fromsrc")

        files_dest = ["file.txt", "subdir2/file2.txt"]
        self._save(self.dest, files_dest, "fromdest")

        # Excluded one file from other_dir and the whole subdir
        merge_directories(self.source, self.dest, excluded=["other_dir/somefile.txt", "subdir"])
        self._assert_equals(self._get_paths(self.dest), ["file.txt",
                                                         "subdir2/file2.txt",
                                                         "other_dir/somefile2.txt"])

        # Excluded one from dest (no sense) and one from origin
        merge_directories(self.source, self.dest, excluded=["subdir2/file2.txt",
                                                            "subdir",
                                                            "other_dir/somefile.txt"])

        self._assert_equals(self._get_paths(self.dest), ["file.txt",
                                                         "subdir2/file2.txt",
                                                         "other_dir/somefile2.txt"])
