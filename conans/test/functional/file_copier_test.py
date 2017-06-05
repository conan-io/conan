import unittest
import os
from conans.util.files import save, load
from conans.test.utils.test_files import temp_folder
import platform
from conans.client.file_copier import FileCopier


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

            for links in (False, True):
                folder2 = temp_folder()
                copier = FileCopier(folder1, folder2)
                copier("*.txt", "texts", links=links)
                if links:
                    self.assertEqual(os.readlink(os.path.join(folder2, "texts/subdir2")), "subdir1")
                self.assertEqual("Hello1", load(os.path.join(folder2, "texts/subdir1/file1.txt")))
                self.assertEqual("Hello1 sub", load(os.path.join(folder2, "texts/subdir1/sub1/file1.txt")))
                self.assertEqual("Hello1", load(os.path.join(folder2, "texts/subdir2/file1.txt")))
                self.assertEqual(['file1.txt', 'sub1'].sort(), os.listdir(os.path.join(folder2, "texts/subdir2")).sort())

            for links in (False, True):
                folder2 = temp_folder()
                copier = FileCopier(folder1, folder2)
                copier("*.txt", "texts", "subdir1", links=links)
                self.assertEqual("Hello1", load(os.path.join(folder2, "texts/file1.txt")))
                self.assertEqual("Hello1 sub", load(os.path.join(folder2, "texts/sub1/file1.txt")))
                self.assertNotIn("subdir2", os.listdir(os.path.join(folder2, "texts")))

    def linked_folder_missing_error_test(self):
        if platform.system() != "Linux" and platform.system() != "Darwin":
            return
 
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
        copier("*.cpp", links=True)
        self.assertEqual(len(os.listdir(folder2)), 0)
        copier("*.txt", links=True)
        self.assertEqual(sorted(os.listdir(folder2)), sorted(["subdir1", "subdir2"]))
        self.assertEqual(os.readlink(os.path.join(folder2, "subdir2")), "subdir1")
        self.assertEqual("Hello1", load(os.path.join(folder2, "subdir1/file1.txt")))
        self.assertEqual("Hello1", load(os.path.join(folder2, "subdir2/file1.txt")))

    def excludes_test(self):
        folder1 = temp_folder()
        sub1 = os.path.join(folder1, "subdir1")
        save(os.path.join(sub1, "file1.txt"), "Hello1")
        save(os.path.join(sub1, "file2.c"), "Hello2")

        folder2 = temp_folder()
        copier = FileCopier(folder1, folder2)
        copier("*.*", "texts", excludes="*.c")
        self.assertEqual(['file1.txt'], os.listdir(os.path.join(folder2, "texts/subdir1")))

        folder1 = temp_folder()
        save(os.path.join(folder1, "MyLib.txt"), "")
        save(os.path.join(folder1, "MyLibImpl.txt"), "")
        save(os.path.join(folder1, "MyLibTests.txt"), "")
        folder2 = temp_folder()
        copier = FileCopier(folder1, folder2)
        copier("*.txt", excludes="*Test*.txt")
        self.assertEqual(set(['MyLib.txt', 'MyLibImpl.txt']), set(os.listdir(folder2)))

        folder2 = temp_folder()
        copier = FileCopier(folder1, folder2)
        copier("*.txt", excludes=("*Test*.txt", "*Impl*"))
        self.assertEqual(['MyLib.txt'], os.listdir(folder2))
