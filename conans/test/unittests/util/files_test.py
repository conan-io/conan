import os
import unittest
from time import sleep

import six

from conans.test.utils.test_files import temp_folder
from conans.util.files import save, to_file_bytes, walk


class SaveTestCase(unittest.TestCase):

    def setUp(self):
        folder = temp_folder()
        self.filepath = os.path.join(folder, "file.txt")

        # Save some content and keep timestamp
        self.content = "my content"
        save(self.filepath, self.content)
        self.timestamp = os.path.getmtime(self.filepath)
        sleep(1)  # precission is seconds, so we need to sleep

    def test_only_if_modified_true(self):
        save(self.filepath, self.content, only_if_modified=True)
        self.assertEqual(self.timestamp, os.path.getmtime(self.filepath))

    def test_only_if_modified_false(self):
        save(self.filepath, self.content, only_if_modified=False)
        self.assertNotEqual(self.timestamp, os.path.getmtime(self.filepath))

    def test_modified_only_true(self):
        save(self.filepath, "other content", only_if_modified=True)
        self.assertNotEqual(self.timestamp, os.path.getmtime(self.filepath))

    def test_modified_only_false(self):
        save(self.filepath, "other content", only_if_modified=False)
        self.assertNotEqual(self.timestamp, os.path.getmtime(self.filepath))

    def test_walk_encoding(self):
        badfilename = "\xE3\x81\x82badfile.txt"
        folder = temp_folder()
        filepath = os.path.join(folder, badfilename)
        save(to_file_bytes(filepath), "contents")
        if six.PY2:
            folder = unicode(folder)
        a_file = [f[0] for _, _, f in walk(folder)][0]
        self.assertTrue(a_file.endswith("badfile.txt"))
