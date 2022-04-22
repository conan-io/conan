import mock
import os
import platform
import unittest

import pytest

from conan.tools.files import copy
from conans.test.utils.test_files import temp_folder
from conans.util.files import load, save


class ToolCopyTest(unittest.TestCase):

    def test_basic(self):
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "subdir1")
        sub2 = os.path.join(folder1, "subdir2")
        save(os.path.join(sub1, "file1.txt"), "hello1")
        save(os.path.join(sub1, "file2.c"), "Hello2")
        save(os.path.join(sub1, "sub1/file1.txt"), "Hello1 sub")
        save(os.path.join(sub1, "sub1/file2.c"), "Hello2 sub")
        save(os.path.join(sub2, "file1.txt"), "2 Hello1")
        save(os.path.join(sub2, "file2.c"), "2 Hello2")

        folder2 = temp_folder()
        copy(None, "*.txt", folder1, os.path.join(folder2, "texts"))
        self.assertEqual("hello1", load(os.path.join(folder2, "texts/subdir1/file1.txt")))
        self.assertEqual("Hello1 sub", load(os.path.join(folder2, "texts/subdir1/sub1/file1.txt")))
        self.assertEqual("2 Hello1", load(os.path.join(folder2, "texts/subdir2/file1.txt")))
        self.assertEqual(['file1.txt'], os.listdir(os.path.join(folder2, "texts/subdir2")))

        folder2 = temp_folder()
        copy(None, "*.txt", os.path.join(folder1, "subdir1"), os.path.join(folder2, "texts"))
        self.assertEqual("hello1", load(os.path.join(folder2, "texts/file1.txt")))
        self.assertEqual("Hello1 sub", load(os.path.join(folder2, "texts/sub1/file1.txt")))
        self.assertNotIn("subdir2", os.listdir(os.path.join(folder2, "texts")))

    @pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
    def test_basic_with_linked_dir(self):
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "subdir1")
        sub2 = os.path.join(folder1, "subdir2")
        os.makedirs(sub1)
        os.symlink("subdir1", sub2)
        save(os.path.join(sub1, "file1.txt"), "hello1")
        save(os.path.join(sub1, "file2.c"), "Hello2")
        save(os.path.join(sub1, "sub1/file1.txt"), "Hello1 sub")
        folder2 = temp_folder()
        copy(None, "*.txt", folder1, os.path.join(folder2, "texts"))
        self.assertEqual(os.readlink(os.path.join(folder2, "texts/subdir2")), "subdir1")
        self.assertEqual("hello1", load(os.path.join(folder2, "texts/subdir1/file1.txt")))
        self.assertEqual("Hello1 sub", load(os.path.join(folder2,
                                                         "texts/subdir1/sub1/file1.txt")))
        self.assertEqual("hello1", load(os.path.join(folder2, "texts/subdir2/file1.txt")))
        self.assertEqual(['file1.txt', 'sub1'].sort(),
                         os.listdir(os.path.join(folder2, "texts/subdir2")).sort())

        folder2 = temp_folder()
        copy(None, "*.txt", os.path.join(folder1, "subdir1"), os.path.join(folder2, "texts"))
        self.assertEqual("hello1", load(os.path.join(folder2, "texts/file1.txt")))
        self.assertEqual("Hello1 sub", load(os.path.join(folder2, "texts/sub1/file1.txt")))
        self.assertNotIn("subdir2", os.listdir(os.path.join(folder2, "texts")))

    @pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
    def test_linked_folder_missing_error(self):
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "subdir1")
        sub2 = os.path.join(folder1, "subdir2")
        os.makedirs(sub1)
        os.symlink("subdir1", sub2)  # @UndefinedVariable
        save(os.path.join(sub1, "file1.txt"), "hello1")
        save(os.path.join(sub1, "file2.c"), "Hello2")
        save(os.path.join(sub1, "sub1/file1.txt"), "Hello1 sub")

        folder2 = temp_folder()
        copy(None, "*.cpp", folder1, folder2)
        # If we don't specify anything, the "subdir2" (symlinked folder) will be there even if it
        # points to an empty folder
        self.assertEqual(os.listdir(folder2), ["subdir2"])
        sub2_abs = os.path.join(folder2, "subdir2")
        assert os.path.islink(sub2_abs)
        assert os.readlink(sub2_abs) == "subdir1"

        # If we specify anything, the "subdir2" (symlinked folder) will be there even if it
        # points to an empty folder
        os.remove(sub2_abs)
        copy(None, "*.cpp", folder1, folder2, copy_symlink_folders=False)
        self.assertEqual(os.listdir(folder2), [])

        copy(None, "*.txt", folder1, folder2)
        self.assertEqual(sorted(os.listdir(folder2)), sorted(["subdir1", "subdir2"]))
        self.assertEqual(os.readlink(os.path.join(folder2, "subdir2")), "subdir1")
        self.assertEqual("hello1", load(os.path.join(folder2, "subdir1/file1.txt")))
        self.assertEqual("hello1", load(os.path.join(folder2, "subdir2/file1.txt")))

    @pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
    def test_linked_relative(self):
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "foo/other/file")
        save(os.path.join(sub1, "file.txt"), "Hello")
        sub2 = os.path.join(folder1, "foo/symlink")
        os.symlink("other/file", sub2)  # @UndefinedVariable

        folder2 = temp_folder()
        copy(None, "*", folder1, folder2)
        symlink = os.path.join(folder2, "foo", "symlink")
        self.assertTrue(os.path.islink(symlink))
        self.assertTrue(load(os.path.join(symlink, "file.txt")), "Hello")

    @pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
    def test_linked_folder_nested(self):
        # https://github.com/conan-io/conan/issues/2959
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "lib/icu/60.2")
        sub2 = os.path.join(folder1, "lib/icu/current")
        os.makedirs(sub1)
        os.symlink("60.2", sub2)  # @UndefinedVariable

        folder2 = temp_folder()
        copied = copy(None, "*.cpp", folder1, folder2)
        self.assertEqual(copied, [])

    @pytest.mark.skipif(platform.system() == "Windows", reason="Requires Symlinks")
    def test_linked_folder_copy_from_linked_folder(self):
        # https://github.com/conan-io/conan/issues/5114
        folder1 = temp_folder(path_with_spaces=False)
        sub_src = os.path.join(folder1, "sub/src")

        src = os.path.join(folder1, "src")
        src_dir = os.path.join(folder1, "src/dir")
        src_dir_link = os.path.join(folder1, "src/dir_link")
        src_dir_file = os.path.join(src_dir, "file.txt")

        dst = os.path.join(folder1, "dst")
        dst_dir = os.path.join(folder1, "dst/dir")
        dst_dir_link = os.path.join(folder1, "dst/dir_link")
        dst_dir_file = os.path.join(dst_dir, "file.txt")

        os.makedirs(dst)
        os.makedirs(sub_src)
        # input src folder should be a symlink
        os.symlink(sub_src, src)
        # folder, file and folder link to copy
        os.mkdir(src_dir)
        save(src_dir_file, "file")
        os.symlink(src_dir, src_dir_link)

        copied = copy(None, "*", src, dst)

        self.assertEqual(copied, [dst_dir_file])
        self.assertEqual(os.listdir(dst), os.listdir(src))
        self.assertTrue(os.path.islink(dst_dir_link))

    def test_excludes(self):
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "subdir1")
        save(os.path.join(sub1, "file1.txt"), "hello1")
        save(os.path.join(sub1, "file2.c"), "Hello2")

        folder2 = temp_folder()
        copy(None, "*.*", folder1, os.path.join(folder2, "texts"), excludes="*.c")
        self.assertEqual(['file1.txt'], os.listdir(os.path.join(folder2, "texts/subdir1")))

        folder1 = temp_folder()
        save(os.path.join(folder1, "MyLib.txt"), "")
        save(os.path.join(folder1, "MyLibImpl.txt"), "")
        save(os.path.join(folder1, "MyLibTests.txt"), "")
        folder2 = temp_folder()
        copy(None, "*.txt", folder1, folder2, excludes="*Test*.txt")
        self.assertEqual({'MyLib.txt', 'MyLibImpl.txt'}, set(os.listdir(folder2)))

        folder2 = temp_folder()
        copy(None, "*.txt", folder1, folder2, excludes=("*Test*.txt", "*Impl*"))
        self.assertEqual(['MyLib.txt'], os.listdir(folder2))

    def test_excludes_camelcase_folder(self):
        # https://github.com/conan-io/conan/issues/8153
        folder1 = temp_folder()
        save(os.path.join(folder1, "UPPER.txt"), "")
        save(os.path.join(folder1, "lower.txt"), "")
        sub2 = os.path.join(folder1, "CamelCaseIgnore")
        save(os.path.join(sub2, "file3.txt"), "")

        folder2 = temp_folder()
        copy(None, "*", folder1, folder2, excludes=["CamelCaseIgnore", "UPPER.txt"])
        self.assertFalse(os.path.exists(os.path.join(folder2, "CamelCaseIgnore")))
        self.assertFalse(os.path.exists(os.path.join(folder2, "UPPER.txt")))
        self.assertTrue(os.path.exists(os.path.join(folder2, "lower.txt")))

        folder2 = temp_folder()
        copy(None, "*", folder1, folder2)
        self.assertTrue(os.path.exists(os.path.join(folder2, "CamelCaseIgnore")))
        self.assertTrue(os.path.exists(os.path.join(folder2, "UPPER.txt")))
        self.assertTrue(os.path.exists(os.path.join(folder2, "lower.txt")))

    def test_multifolder(self):
        src_folder1 = temp_folder()
        src_folder2 = temp_folder()
        save(os.path.join(src_folder1, "file1.txt"), "hello1")
        save(os.path.join(src_folder2, "file2.txt"), "Hello2")

        dst_folder = temp_folder()
        copy(None, "*", src_folder1, dst_folder)
        copy(None, "*", src_folder2, dst_folder)
        self.assertEqual(['file1.txt', 'file2.txt'],
                         sorted(os.listdir(dst_folder)))

    @mock.patch('shutil.copy2')
    def test_avoid_repeat_copies(self, copy2_mock):
        src_folders = [temp_folder() for _ in range(2)]
        for index, src_folder in enumerate(src_folders):
            save(os.path.join(src_folder, "sub", "file%d.txt" % index),
                 "Hello%d" % index)

        dst_folder = temp_folder()

        for src_folder in src_folders:
            copy(None, "*", os.path.join(src_folder, "sub"), dst_folder)

        self.assertEqual(copy2_mock.call_count, len(src_folders))

    def test_ignore_case(self):
        src_folder = temp_folder()
        save(os.path.join(src_folder, "FooBar.txt"), "Hello")

        dst_folder = temp_folder()
        copy(None, "foobar.txt", src_folder, dst_folder, ignore_case=False)
        self.assertEqual([], os.listdir(dst_folder))

        dst_folder = temp_folder()
        copy(None, "FooBar.txt", src_folder, dst_folder, ignore_case=False)
        self.assertEqual(["FooBar.txt"], os.listdir(dst_folder))

        dst_folder = temp_folder()
        copy(None, "foobar.txt", src_folder, dst_folder, ignore_case=True)
        self.assertEqual(["FooBar.txt"], os.listdir(dst_folder))

    def test_ignore_case_excludes(self):
        src_folder = temp_folder()
        save(os.path.join(src_folder, "file.h"), "")
        save(os.path.join(src_folder, "AttributeStorage.h"), "")
        save(os.path.join(src_folder, "sub/file.h"), "")
        save(os.path.join(src_folder, "sub/AttributeStorage.h"), "")

        dst_folder = temp_folder()
        # Exclude pattern will match AttributeStorage
        copy(None, "*.h", src_folder, os.path.join(dst_folder, "include"),
             excludes="*Test*")
        self.assertEqual(["include"], os.listdir(dst_folder))
        self.assertEqual(sorted(["file.h", "sub"]),
                         sorted(os.listdir(os.path.join(dst_folder, "include"))))
        self.assertEqual(["file.h"], os.listdir(os.path.join(dst_folder, "include", "sub")))

        dst_folder = temp_folder()
        # Exclude pattern will not match AttributeStorage if ignore_case=False
        copy(None, "*.h", src_folder, os.path.join(dst_folder, "include"), excludes="*Test*",
             ignore_case=False)
        self.assertEqual(["include"], os.listdir(dst_folder))
        self.assertEqual(sorted(["AttributeStorage.h", "file.h", "sub"]),
                         sorted(os.listdir(os.path.join(dst_folder, "include"))))
        self.assertEqual(sorted(["AttributeStorage.h", "file.h"]),
                         sorted(os.listdir(os.path.join(dst_folder, "include", "sub"))))
