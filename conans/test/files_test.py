import unittest
import os
from conans.util.files import save, load
from conans.client.file_copier import FileCopier
from conans.test.utils.test_files import temp_folder
import platform

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
        copier = FileCopier(folder1, folder2)
        copier("*.txt", "texts")
        self.assertEqual("Hello1", load(os.path.join(folder2, "texts/subdir1/file1.txt")))
        self.assertEqual("Hello1 sub", load(os.path.join(folder2, "texts/subdir1/sub1/file1.txt")))
        self.assertEqual("2 Hello1", load(os.path.join(folder2, "texts/subdir2/file1.txt")))
        self.assertEqual(['file1.txt'], os.listdir(os.path.join(folder2, "texts/subdir2")))

        folder2 = temp_folder()
        copier = FileCopier(folder1, folder2)
        copier("*.txt", "texts", "subdir1")
        self.assertEqual("Hello1", load(os.path.join(folder2, "texts/file1.txt")))
        self.assertEqual("Hello1 sub", load(os.path.join(folder2, "texts/sub1/file1.txt")))
        self.assertNotIn("subdir2", os.listdir(os.path.join(folder2, "texts")))

    def basic_with_linked_dir_test(self):
        if platform.system() == "Linux" or platform.system() == "Darwin":
            folder1 = temp_folder()
            sub1 = os.path.join(folder1, "subdir1")
            sub2 = os.path.join(folder1, "subdir2")
            os.makedirs(sub1)
            os.symlink("subdir1", sub2)
            save(os.path.join(sub1, "file1.txt"), "Hello1")
            save(os.path.join(sub1, "file2.c"), "Hello2")
            save(os.path.join(sub1, "sub1/file1.txt"), "Hello1 sub")

            folder2 = temp_folder()
            copier = FileCopier(folder1, folder2)
            copier("*.txt", "texts")
            self.assertEqual("Hello1", load(os.path.join(folder2, "texts/subdir1/file1.txt")))
            self.assertEqual("Hello1 sub", load(os.path.join(folder2, "texts/subdir1/sub1/file1.txt")))
            self.assertEqual("Hello1", load(os.path.join(folder2, "texts/subdir2/file1.txt")))
            self.assertEqual(['file1.txt', 'sub1'].sort(), os.listdir(os.path.join(folder2, "texts/subdir2")).sort())

            folder2 = temp_folder()
            copier = FileCopier(folder1, folder2)
            copier("*.txt", "texts", "subdir1")
            self.assertEqual("Hello1", load(os.path.join(folder2, "texts/file1.txt")))
            self.assertEqual("Hello1 sub", load(os.path.join(folder2, "texts/sub1/file1.txt")))
            self.assertNotIn("subdir2", os.listdir(os.path.join(folder2, "texts")))