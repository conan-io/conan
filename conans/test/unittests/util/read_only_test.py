import os
import unittest

from conans.test.utils.test_files import temp_folder
from conans.util.files import load, make_read_only, save


class ReadOnlyTest(unittest.TestCase):

    def test_read_only(self):
        folder = temp_folder()
        f = os.path.join(folder, "file.txt")
        save(f, "Hello World")
        make_read_only(folder)
        with self.assertRaises(IOError):
            save(f, "Bye World")
        self.assertEqual("Hello World", load(f))
