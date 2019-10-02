import os
import platform
import unittest

from conans.client.file_copier import FileCopier
from conans.test.utils.test_files import temp_folder
from conans.util.files import load, save


class FileCopierTest(unittest.TestCase):

    def basic_test(self):
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "subdir1")
        sub2 = os.path.join(folder1, "subdir2")
        save(os.path.join(sub1, "file1.txt"), "Hello1")
        save(os.path.join(sub1, "file2.c"), "Hello2")
        save(os.path.join(sub1, "sub1/file1.txt"), "Hello1 sub")
        save(os.path.join(sub1, "sub1/file2.c"), "Hello2 sub")
        save(os.path.join(sub2, "file1.txt"), "2 Hello1")
        save(os.path.join(sub2, "file2.c"), "2 Hello2")

        folder2 = temp_folder()
        copier = FileCopier([folder1], folder2)
        copier("*.txt", "texts")
        self.assertEqual("Hello1", load(os.path.join(folder2, "texts/subdir1/file1.txt")))
        self.assertEqual("Hello1 sub", load(os.path.join(folder2, "texts/subdir1/sub1/file1.txt")))
        self.assertEqual("2 Hello1", load(os.path.join(folder2, "texts/subdir2/file1.txt")))
        self.assertEqual(['file1.txt'], os.listdir(os.path.join(folder2, "texts/subdir2")))

        folder2 = temp_folder()
        copier = FileCopier([folder1], folder2)
        copier("*.txt", "texts", "subdir1")
        self.assertEqual("Hello1", load(os.path.join(folder2, "texts/file1.txt")))
        self.assertEqual("Hello1 sub", load(os.path.join(folder2, "texts/sub1/file1.txt")))
        self.assertNotIn("subdir2", os.listdir(os.path.join(folder2, "texts")))

    @unittest.skipUnless(platform.system() != "Windows", "Requires Symlinks")
    def basic_with_linked_dir_test(self):
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "subdir1")
        sub2 = os.path.join(folder1, "subdir2")
        os.makedirs(sub1)
        os.symlink("subdir1", sub2) # @UndefinedVariable
        save(os.path.join(sub1, "file1.txt"), "Hello1")
        save(os.path.join(sub1, "file2.c"), "Hello2")
        save(os.path.join(sub1, "sub1/file1.txt"), "Hello1 sub")

        for links in (False, True):
            folder2 = temp_folder()
            copier = FileCopier([folder1], folder2)
            copier("*.txt", "texts", links=links)
            if links:
                self.assertEqual(os.readlink(os.path.join(folder2, "texts/subdir2")), "subdir1") # @UndefinedVariable
            self.assertEqual("Hello1", load(os.path.join(folder2, "texts/subdir1/file1.txt")))
            self.assertEqual("Hello1 sub", load(os.path.join(folder2, "texts/subdir1/sub1/file1.txt")))
            self.assertEqual("Hello1", load(os.path.join(folder2, "texts/subdir2/file1.txt")))
            self.assertEqual(['file1.txt', 'sub1'].sort(), os.listdir(os.path.join(folder2, "texts/subdir2")).sort())

        for links in (False, True):
            folder2 = temp_folder()
            copier = FileCopier([folder1], folder2)
            copier("*.txt", "texts", "subdir1", links=links)
            self.assertEqual("Hello1", load(os.path.join(folder2, "texts/file1.txt")))
            self.assertEqual("Hello1 sub", load(os.path.join(folder2, "texts/sub1/file1.txt")))
            self.assertNotIn("subdir2", os.listdir(os.path.join(folder2, "texts")))

    @unittest.skipUnless(platform.system() != "Windows", "Requires Symlinks")
    def linked_folder_missing_error_test(self):
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "subdir1")
        sub2 = os.path.join(folder1, "subdir2")
        os.makedirs(sub1)
        os.symlink("subdir1", sub2)  # @UndefinedVariable
        save(os.path.join(sub1, "file1.txt"), "Hello1")
        save(os.path.join(sub1, "file2.c"), "Hello2")
        save(os.path.join(sub1, "sub1/file1.txt"), "Hello1 sub")

        folder2 = temp_folder()
        copier = FileCopier([folder1], folder2)
        copier("*.cpp", links=True)
        self.assertEqual(os.listdir(folder2), [])
        copier("*.txt", links=True)
        self.assertEqual(sorted(os.listdir(folder2)), sorted(["subdir1", "subdir2"]))
        self.assertEqual(os.readlink(os.path.join(folder2, "subdir2")), "subdir1")  # @UndefinedVariable
        self.assertEqual("Hello1", load(os.path.join(folder2, "subdir1/file1.txt")))
        self.assertEqual("Hello1", load(os.path.join(folder2, "subdir2/file1.txt")))

    @unittest.skipUnless(platform.system() != "Windows", "Requires Symlinks")
    def linked_relative_test(self):
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "foo/other/file")
        save(os.path.join(sub1, "file.txt"), "Hello")
        sub2 = os.path.join(folder1, "foo/symlink")
        os.symlink("other/file", sub2)  # @UndefinedVariable

        folder2 = temp_folder()
        copier = FileCopier([folder1], folder2)
        copier("*", links=True)
        symlink = os.path.join(folder2, "foo", "symlink")
        self.assertTrue(os.path.islink(symlink))
        self.assertTrue(load(os.path.join(symlink, "file.txt")), "Hello")

    @unittest.skipUnless(platform.system() != "Windows", "Requires Symlinks")
    def linked_folder_nested_test(self):
        # https://github.com/conan-io/conan/issues/2959
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "lib/icu/60.2")
        sub2 = os.path.join(folder1, "lib/icu/current")
        os.makedirs(sub1)
        os.symlink("60.2", sub2)  # @UndefinedVariable

        folder2 = temp_folder()
        copier = FileCopier([folder1], folder2)
        copied = copier("*.cpp", links=True)
        self.assertEqual(copied, [])

    @unittest.skipUnless(platform.system() != "Windows", "Requires Symlinks")
    def linked_folder_copy_from_linked_folder_test(self):
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

        copier = FileCopier([src], dst)
        copied = copier("*", symlinks=True)

        self.assertEqual(copied, [dst_dir_file])
        self.assertEqual(os.listdir(dst), os.listdir(src))
        self.assertTrue(os.path.islink(dst_dir_link))

    def excludes_test(self):
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "subdir1")
        save(os.path.join(sub1, "file1.txt"), "Hello1")
        save(os.path.join(sub1, "file2.c"), "Hello2")

        folder2 = temp_folder()
        copier = FileCopier([folder1], folder2)
        copier("*.*", "texts", excludes="*.c")
        self.assertEqual(['file1.txt'], os.listdir(os.path.join(folder2, "texts/subdir1")))

        folder1 = temp_folder()
        save(os.path.join(folder1, "MyLib.txt"), "")
        save(os.path.join(folder1, "MyLibImpl.txt"), "")
        save(os.path.join(folder1, "MyLibTests.txt"), "")
        folder2 = temp_folder()
        copier = FileCopier([folder1], folder2)
        copier("*.txt", excludes="*Test*.txt")
        self.assertEqual(set(['MyLib.txt', 'MyLibImpl.txt']), set(os.listdir(folder2)))

        folder2 = temp_folder()
        copier = FileCopier([folder1], folder2)
        copier("*.txt", excludes=("*Test*.txt", "*Impl*"))
        self.assertEqual(['MyLib.txt'], os.listdir(folder2))
