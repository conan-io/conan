import unittest
from conans.test.utils.test_files import temp_folder
from conans.util.files import make_read_only, save, load
import os


class ReadOnlyTest(unittest.TestCase):

    def read_only_test(self):
        folder = temp_folder()
        f = os.path.join(folder, "file.txt")
        save(f, "Hello World")
        make_read_only(folder)
        with self.assertRaises(IOError):
            save(f, "Bye World")
        self.assertEqual("Hello World", load(f))